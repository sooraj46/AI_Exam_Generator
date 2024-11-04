import os
import json
from flask import Blueprint,current_app, render_template, request, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
import google.generativeai as genai
from ..models import Document, Question, db,QuizResponse
from flask_jwt_extended import jwt_required, get_jwt_identity
from google.ai.generativelanguage_v1beta.types import content
import time
from ..utils.decorators import roles_required

examgenerator_bp = Blueprint('examgenerator', __name__, template_folder='templates/exam')
ALLOWED_EXTENSIONS = {'pdf'}
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

#current_app.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#upload document & generate exam
@examgenerator_bp.route('generate-exam', methods=['GET', 'POST'])
@jwt_required()
@roles_required('Individual')
def upload_and_generate():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return render_template('exam/generateexam.html')

        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return render_template('exam/generateexam.html')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            user_id = get_jwt_identity()
            current_app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
            file.save(filepath)

            document = Document(filename=filename, filepath=filepath, owner_id=user_id)
            db.session.add(document)
            db.session.commit()
            document_id = document.id

            try:
                generate_and_save_questions(filepath, document_id)
                flash('File uploaded and questions generated successfully!')
                return render_template('exam/generateexam.html', document_id=document_id, documents=Document.query.filter_by(owner_id=get_jwt_identity()).all())
            except Exception as e:
                flash(f'Error generating or saving questions: {e}')
                db.session.rollback()
                return render_template('exam/generateexam.html', documents=Document.query.filter_by(owner_id=get_jwt_identity()).all())

        else:
            flash('Invalid file type. Please upload a PDF file.')
            return render_template('exam/generateexam.html', documents=Document.query.filter_by(owner_id=get_jwt_identity()).all())

    documents = Document.query.filter_by(owner_id=get_jwt_identity()).all()
    return render_template('exam/generateexam.html', documents=documents)


#generate questions and save to DB
def generate_and_save_questions(filepath, document_id):
    try:
      # Prepare the prompt
        prompt = f"""
        You are an expert in creating educational content. Based on the following document, generate **40 multiple-choice questions** in **JSON format**. Each question should include the following fields:

            - `"question"`: The question text.
            - `"options"`: An array of **4** answer options.
            - `"correct_answer"`: The correct option text.
            - `"explanation"`: A brief explanation of why the answer is correct.

            **Requirements:**

            1. **Content-Based**: All questions and answers must be entirely based on the information provided in the document below. Do not include any external information or assumptions.
            2. **Clarity and Precision**: Ensure that each question is clear and unambiguous. The options should be plausible to avoid obvious elimination.
            3. **JSON Structure**: The output must be a valid JSON array containing 10 objects, each representing a question with the specified fields.

            **Additional Notes:**

            - The `"options"` array should contain exactly four distinct options.
            - Only one option should be marked as the `"correct_answer"`.
            - The `"explanation"` should provide a concise reason why the selected answer is correct, enhancing the educational value of the question.
            - Correct ansewer should be distributed almost equally with all of the option
        """
        
        generation_config = {
            "temperature": 1.5,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_schema": content.Schema(
                type=content.Type.OBJECT,
                enum=[],
                required=["questions"],
                properties={
                    "questions": content.Schema(
                        type=content.Type.ARRAY,
                        items=content.Schema(
                            type=content.Type.OBJECT,
                            enum=[],
                            required=["question", "options", "correct_answer", "explanation"],
                            properties={
                                "question": content.Schema(
                                    type=content.Type.STRING,
                                ),
                                "options": content.Schema(
                                    type=content.Type.ARRAY,
                                    items=content.Schema(
                                        type=content.Type.STRING,
                                    ),
                                ),
                                "correct_answer": content.Schema(
                                    type=content.Type.STRING,
                                ),
                                "explanation": content.Schema(
                                    type=content.Type.STRING,
                                ),
                            },
                        ),
                    ),
                },
            ),
            "response_mime_type": "application/json",
        }
        
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config, system_instruction=prompt)
        myfile = genai.upload_file(path=filepath, mime_type="application/pdf")
        wait_for_files_active([myfile])
        response = model.generate_content([myfile])

        generated_text = response.text
        myfile.delete()

        generated_text = response.text
        try:
            questions_data = json.loads(generated_text)["questions"]
        except (json.JSONDecodeError, KeyError) as e:
            raise Exception(f"Invalid JSON response from Gemini: {e}") from None

        for q in questions_data:
            if len(q.get('options', [])) == 4:
                question = Question(
                    question_text=q['question'],  # Changed 'question' to 'question_text'
                    options=json.dumps(q['options']),
                    correct_answer=q['correct_answer'],
                    explanation=q['explanation'],
                    document_id=document_id
                )
                db.session.add(question)
        db.session.commit()

    except Exception as e:
        raise Exception(f"Error generating or saving questions: {e}") from None

def wait_for_files_active(files):
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
        


@examgenerator_bp.route('/delete_document/<int:document_id>', methods=['POST'])
@jwt_required()
@roles_required('Individual')
def delete_document(document_id):
    try:
        questions = Question.query.filter_by(document_id=document_id).all()
        for question in questions:
        # Delete all responses linked to this question
            QuizResponse.query.filter_by(question_id=question.id).delete()
            db.session.delete(question)
            db.session.commit() # Commit question and response deletion
    except Exception as e:
        flash(f"Error deleting questions or responses: {e}", 'danger')
    db.session.rollback()
   # return redirect(url_for('examgenerator.upload_and_generate'))

    try:
        document = Document.query.get_or_404(document_id)
        current_user = get_jwt_identity()

        if document.owner_id != current_user:
            flash('You do not have permission to delete this document.', 'danger')
            return redirect(url_for('examgenerator.upload_and_generate'))

        # Crucial: Delete associated questions (important!)
        try:
            questions = Question.query.filter_by(document_id=document_id).all()
            for question in questions:
                db.session.delete(question)
            db.session.commit() # Commit question deletion
        except Exception as e:
          flash(f"Error deleting questions: {e}", 'danger')
          db.session.rollback()
          return redirect(url_for('examgenerator.upload_and_generate'))


        # Delete the document itself
        try:
            db.session.delete(document)
            db.session.commit()  # Commit document deletion
        except Exception as e:
           flash(f"Error deleting document: {e}", 'danger')
           db.session.rollback()
           return redirect(url_for('examgenerator.upload_and_generate'))



        #Attempt file deletion.  Critical to put in a try-except.
        try:
            if os.path.exists(document.filepath):
                os.remove(document.filepath)
        except Exception as e:
            flash(f"Error deleting file: {e}", 'danger')
            # No need for rollback here. File deletion failure doesn't invalidate db operations
            return redirect(url_for('examgenerator.upload_and_generate'))

        flash('Document deleted successfully!', 'success')
        return redirect(url_for('examgenerator.upload_and_generate'))


    except Exception as e:
        flash(f'Error deleting document: {e}', 'danger')
        db.session.rollback()
        return redirect(url_for('examgenerator.upload_and_generate'))


# New function to process questions for existing documents
@examgenerator_bp.route('/process_existing_documents', methods=['POST'])
@jwt_required()
@roles_required('Individual')
def process_existing_documents():
    user_id = get_jwt_identity()
    documents = Document.query.filter_by(owner_id=user_id).all()

    for document in documents:
        if not document.questions:  # Check if questions already exist
            try:
                generate_and_save_questions(document.filepath, document.id)
                flash(f'Questions generated for {document.filename} successfully!', 'success')
            except Exception as e:
                flash(f'Error generating questions for {document.filename}: {e}', 'danger')
    
    return redirect(url_for('examgenerator.upload_and_generate'))