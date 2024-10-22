from datetime import time
import json
import os
from flask_bcrypt import Bcrypt
from flask import Blueprint, current_app, request, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Document, Question, db, User, Group, Role
from ..utils.decorators import roles_required
import google.generativeai as genai
from werkzeug.utils import secure_filename
from typing_extensions import TypedDict, List
from google.ai.generativelanguage_v1beta.types import content


bcrypt = Bcrypt()
conductor_bp = Blueprint('conductor', __name__, template_folder='../templates/conductor')

# Configure Gemini AI
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_gemini(path: str, mime_type: str = None):
    """
    https://ai.google.dev/gemini-api/docs/prompting_with_media
    """
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file


def wait_for_files_active(files):
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    

@conductor_bp.route('/manage-exam-takers', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def manage_exam_takers():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        

        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('conductor.manage_exam_takers'))
        
        exam_taker_role = Role.query.filter_by(name='ExamTaker').first()

        if not exam_taker_role:
            flash('Exam Taker role not found.', 'danger')
            return redirect(url_for('conductor.manage_exam_takers'))
        
        new_exam_taker = User(username=username, email=email)
        new_exam_taker.set_password(password)
        new_exam_taker.roles.append(exam_taker_role)
        db.session.add(new_exam_taker)
        db.session.commit()

        flash('Exam Taker created successfully!', 'success')
        return redirect(url_for('conductor.manage_exam_takers'))

    # Query all Exam Takers to display in the template
    exam_takers = User.query.filter(User.roles.any(Role.name == 'ExamTaker')).all()

    return render_template('conductor/manage_exam_takers.html', exam_takers=exam_takers)

# Route for deleting an Exam Taker
@conductor_bp.route('/delete-exam-taker/<int:user_id>', methods=['POST'])
@jwt_required()
@roles_required('ExamConductor')
def delete_exam_taker(user_id):
    exam_taker = User.query.get_or_404(user_id)

    # Ensure we only delete Exam Takers
    if 'ExamTaker' not in [role.name for role in exam_taker.roles]:
        flash('You can only delete Exam Takers.', 'danger')
        return redirect(url_for('conductor.manage_exam_takers'))

    db.session.delete(exam_taker)
    db.session.commit()

    flash(f'Exam Taker {exam_taker.username} has been deleted successfully.', 'success')
    return redirect(url_for('conductor.manage_exam_takers'))

@conductor_bp.route('/manage-groups', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def manage_groups():
    current_user_id = get_jwt_identity()
    if request.method == 'POST':
        data = request.form
        group_name = data.get('group_name')
        user_ids = request.form.getlist('user_ids')  # List of user IDs to add to the group

        if Group.query.filter_by(name=group_name).first():
            flash('Group name already exists.', 'danger')
            return redirect(url_for('conductor.manage_groups'))

        group = Group(name=group_name, created_by=current_user_id)
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user:
                group.users.append(user)
        
        db.session.add(group)
        db.session.commit()
        flash('Group created successfully.', 'success')
        return redirect(url_for('conductor.manage_groups'))

    groups = Group.query.filter_by(created_by=current_user_id).all()
    exam_takers = User.query.join(User.roles).filter(Role.name == 'ExamTaker').all()
    return render_template('manage_groups.html', groups=groups, exam_takers=exam_takers)

@conductor_bp.route('/toggle-access', methods=['POST'])
@jwt_required()
@roles_required('ExamConductor')
def toggle_access():
    data = request.form
    group_id = data.get('group_id')

    group = Group.query.get(group_id)
    if group:
        group.access = not group.access
        db.session.commit()
        flash('Group access updated successfully.', 'success')
    else:
        flash('Group not found.', 'danger')
    return redirect(url_for('conductor.manage_groups'))

@conductor_bp.route('/delete-group/<int:group_id>', methods=['POST'])
@jwt_required()
@roles_required('ExamConductor')
def delete_group(group_id):
    group_to_delete = Group.query.get_or_404(group_id)
    
    db.session.delete(group_to_delete)
    db.session.commit()
    flash(f'Group {group_to_delete.name} has been deleted successfully.', 'success')
    
@conductor_bp.route('/upload-document', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def upload_document():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            user_id = get_jwt_identity()
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
            file.save(filepath)

            # Save the document in the database
            document = Document(filename=filename, filepath=filepath, owner_id=user_id)
            db.session.add(document)
            db.session.commit()

            flash('File uploaded successfully!', 'success')
        else:
            flash('Invalid file type. Please upload a PDF file.', 'danger')
                
    uploaded_documents = Document.query.filter_by(owner_id=get_jwt_identity()).all()
    return render_template('conductor/upload_document.html' , documents=uploaded_documents)

@conductor_bp.route('/generate-questions/<int:document_id>', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def generate_questions(document_id):
    document = Document.query.get_or_404(document_id)
    user_id = get_jwt_identity()
    if document.owner_id != user_id:
        flash('You do not have permission to access this document.', 'danger')
        return redirect(url_for('conductor.upload_document'))

    # Generate questions using Gemini AI
    try:
        # Prepare the prompt
        prompt = f"""
        Based on the following content, generate 10 multiple-choice questions in JSON format.
        Each question should include:
        - "question": The question text.
        - "options": An array of 4 options.
        - "correct_answer": The correct option.
        - "explanation": A brief explanation.
        Question and Answer should be entirely based on the document alone
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
        myfile = genai.upload_file(path= document.filepath, mime_type="application/pdf")
        wait_for_files_active([myfile])
        response = model.generate_content([myfile])

        generated_text = response.text

        # Parse the generated text to extract questions
        questions = parse_generated_questions(generated_text, document)
        db.session.add_all(questions)
        
        db.session.commit()

        flash('Questions generated successfully!', 'success')
        return render_template('conductor/view_questions.html', questions=questions, document=document)
    except Exception as e:
        flash(f'Error generating questions: {e}', 'danger')
        return redirect(url_for('conductor.upload_document'))

def parse_generated_questions(generated_text, document):
    """
    Parse the generated text (in JSON format) to extract questions.
    """
    try:
        questions_data = json.loads(generated_text.replace('\n', ''))
        questionsJSON = questions_data['questions']
        questions = []
        for q in questionsJSON:
            question = Question(
                question_text=q['question'],
                options=json.dumps(q['options']),
                correct_answer=q['correct_answer'],
                explanation=q.get('explanation', ''),
                document_id =document.id
            )
            questions.append(question)
        return questions
    except json.JSONDecodeError as e:
        flash('Error parsing generated questions. Please ensure the AI output is in valid JSON format.', 'danger')
        return []
    
@conductor_bp.route('/delete_document/<int:document_id>', methods=['POST'])
@jwt_required()
@roles_required('ExamConductor')
def delete_document(document_id):
    # Fetch the document from the database
    document = Document.query.get_or_404(document_id)
    
    # Ensure the logged-in user is the owner of the document
    user_id = get_jwt_identity()
    if document.owner_id != user_id:
        flash('You do not have permission to delete this document.', 'danger')
        return redirect(url_for('conductor.upload_document'))
    
    # Try to remove the file from the filesystem
    try:
        if os.path.exists(document.filepath):
            os.remove(document.filepath)
    except Exception as e:
        flash(f"Error deleting file from filesystem: {e}", 'danger')
        return redirect(url_for('conductor.upload_document'))
    
    # Remove the document entry from the database
    db.session.delete(document)
    db.session.commit()
    
    flash('Document has been successfully deleted.', 'success')
    return redirect(url_for('conductor.upload_document'))