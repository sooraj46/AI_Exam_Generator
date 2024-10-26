from datetime import time
import json
import os
from flask_bcrypt import Bcrypt
from flask import Blueprint, current_app, request, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Document, Exam, ExamResponse, Question, db, User, Group, Role
from ..utils.decorators import roles_required
import google.generativeai as genai
from werkzeug.utils import secure_filename
from typing_extensions import TypedDict, List
from google.ai.generativelanguage_v1beta.types import content
import uuid
import random
from datetime import datetime, timedelta
from flask import session 



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
    
@conductor_bp.route('/create-exam/<int:document_id>', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def create_exam(document_id):
    document = Document.query.get_or_404(document_id)
    current_user_id = get_jwt_identity()
    # Fetch groups created by the current conductor
    groups = Group.query.filter_by(created_by=current_user_id).all()
    if request.method == 'POST':
        exam_name = request.form.get('exam_name')
        group_id = request.form.get('group_id')
        time_limit = int(request.form.get('time_limit'))
        group = Group.query.get(group_id)
        if not group or group.created_by != current_user_id:
            flash('Invalid group selected.', 'danger')
            return redirect(url_for('conductor.create_exam', document_id=document_id))
        # Generate a unique access code
        access_code = str(uuid.uuid4())[:8]
        # Create the exam
        exam = Exam(
            name=exam_name,
            document_id=document.id,
            access_code=access_code,
            group_id=group.id,
            time_limit=time_limit
        )
        # Associate questions with the exam
        questions = Question.query.filter_by(document_id=document.id).all()
        for question in questions:
            question.exam = exam
        db.session.add(exam)
        db.session.commit()
        flash('Exam created successfully!', 'success')
        return redirect(url_for('conductor.list_exams', exam_id=exam.id))
    return render_template('conductor/create_exam.html', document=document, groups=groups)

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
        myfile = genai.upload_file(path= document.filepath, mime_type="application/pdf")
        wait_for_files_active([myfile])
        response = model.generate_content([myfile])

        generated_text = response.text
        myfile.delete()

        # Parse the generated text to extract questions
        questions = parse_generated_questions(generated_text)
        # Serialize the questions to JSON
        questions_json = json.dumps(questions)

        # Store the generated questions in the session
        session['generated_questions'] = questions_json

        flash('Questions generated successfully!', 'success')
        return render_template('conductor/view_questions.html', questions=questions, document=document)
    except Exception as e:
        flash(f'Error generating questions: {e}', 'danger')
        return redirect(url_for('conductor.upload_document'))

def parse_generated_questions(generated_text):
    """
    Parse the generated text (in JSON format) to extract questions.
    """
    try:
        questions_data = json.loads(generated_text.replace('\n', ''))
        return questions_data['questions']  # Return the list of question dicts
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
    Question.query.filter_by(document_id=document_id).delete()
    db.session.delete(document)
    db.session.commit()
    
    flash('Document has been successfully deleted.', 'success')
    return redirect(url_for('conductor.upload_document'))


@conductor_bp.route('/select-questions/<int:document_id>', methods=['GET', 'POST'])
@jwt_required()
@roles_required('ExamConductor')
def select_questions(document_id):
    document = Document.query.get_or_404(document_id)
    user_id = get_jwt_identity()
    if document.owner_id != user_id:
        flash('You do not have permission to access this document.', 'danger')
        return redirect(url_for('conductor.upload_document'))

    # Retrieve the generated questions from the session
    questions_json = session.get('generated_questions')
    if not questions_json:
        flash('No generated questions found. Please generate questions first.', 'danger')
        return redirect(url_for('conductor.generate_questions', document_id=document_id))

    questions = json.loads(questions_json)

    if request.method == 'POST':
        # Process the selected questions and create the exam

        # Get exam details from the form
        exam_name = request.form.get('exam_name')
        group_id = request.form.get('group_id')
        time_limit = int(request.form.get('time_limit'))

        # Verify the group
        group = Group.query.get(group_id)
        if not group or group.created_by != user_id:
            flash('Invalid group selected.', 'danger')
            return redirect(url_for('conductor.select_questions', document_id=document_id))

        # Get selected questions from the form
        selected_indices = request.form.getlist('selected_questions')

        if not selected_indices:
            flash('Please select at least one question for the exam.', 'danger')
            return redirect(url_for('conductor.select_questions', document_id=document_id))

        # Filter the selected questions
        selected_questions = [questions[int(idx)] for idx in selected_indices]

        # Create the exam
        access_code = str(uuid.uuid4())[:8]
        exam = Exam(
            name=exam_name,
            document_id=document.id,
            access_code=access_code,
            group_id=group.id,
            time_limit=time_limit
        )
        db.session.add(exam)
        db.session.commit()

        # Save the selected questions to the database
        for q_data in selected_questions:
            question = Question(
                question_text=q_data['question'],
                options=json.dumps(q_data['options']),
                correct_answer=q_data['correct_answer'],
                explanation=q_data.get('explanation', ''),
                document_id=document.id,
                exam_id=exam.id
            )
            db.session.add(question)
        db.session.commit()

        # Clear the generated questions from the session
        session.pop('generated_questions', None)

        flash('Exam created successfully!', 'success')
        return redirect(url_for('conductor.list_exams'))

    else:
        # GET request: Display the questions with selection options
        # Get groups created by the current conductor
        groups = Group.query.filter_by(created_by=user_id).all()

        return render_template('conductor/select_questions.html', questions=questions, document=document, groups=groups)

@conductor_bp.route('/exams', methods=['GET'])
@jwt_required()
@roles_required('ExamConductor')
def list_exams():
    current_user_id = get_jwt_identity()
    # Get all exams created by the current conductor
    exams = Exam.query.join(Group).filter(Group.created_by == current_user_id).all()

    exams_with_summaries = []
    for exam in exams:
        total_users = exam.group.users.count()
        taken_by = len([er for er in exam.exam_responses if er.submitted_at is not None])
        exams_with_summaries.append({
            'exam': exam,
            'total_users': total_users,
            'taken_by': taken_by,
        })
    return render_template('conductor/exams.html', exams=exams_with_summaries)

@conductor_bp.route('/exam/<int:exam_id>', methods=['GET'])
@jwt_required()
@roles_required('ExamConductor')
def exam_details(exam_id):
    current_user_id = get_jwt_identity()
    exam = Exam.query.get_or_404(exam_id)
    # Verify the exam's group was created by the current conductor
    if exam.group.created_by != current_user_id:
        flash('You do not have permission to view this exam.', 'danger')
        return redirect(url_for('conductor.list_exams'))

    # Get all users in the group
    group_users = exam.group.users.all()
    # For each user, check if they have taken the exam
    user_statuses = []
    for user in group_users:
        exam_response = ExamResponse.query.filter_by(exam_id=exam.id, user_id=user.id).first()
        taken = exam_response is not None and exam_response.submitted_at is not None
        user_statuses.append({
            'user': user,
            'taken': taken,
            'score': exam_response.score if taken else None,
            'submitted_at': exam_response.submitted_at if taken else None,
        })

    return render_template('conductor/exam_details.html', exam=exam, user_statuses=user_statuses)

