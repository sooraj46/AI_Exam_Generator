from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session
from flask_session import Session
import json
from flask import  current_app  # Add current_app here
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import psycopg2
from ..models import db, Question, Document, QuizAttempt, QuizResponse  # Make sure 'db' is imported from models
from flask_sqlalchemy import SQLAlchemy

# Define the blueprint
qagen_bp = Blueprint('QAGenerator', __name__, template_folder='../templates/exam')

logging.basicConfig(level=logging.DEBUG)
logging.debug("json module loaded successfully.") 

# from app.routes.QAGenerator import app as QAGenerator_app
# qagen_bp.register_blueprint(QAGenerator_app)

# Database configuration
""" username = 'postgres'
password = 'admin%40123'  # Use the encoded password
database = 'QuizDB'
host = 'localhost'
port = '5432' """

# Creating the connection string
# qagen_bp.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{username}:{password}@{host}:{port}/{database}'
# qagen_bp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Optional, to suppress a warning

# # Initialize SQLAlchemy
# db = SQLAlchemy(qagen_bp)

# Flask session setup

# Session(qagen_bp)
# qagen_bp.secret_key = str(uuid.uuid4())

# # Configure logging
# logging.basicConfig(level=logging.DEBUG)

# # Limit file size to 1 MB
# qagen_bp.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 MB

# def load_quiz_data_from_file(file):
#     """Load quiz data from a file object."""
#     try:
#         file_content = file.read().decode('utf-8')  # Decode the file bytes to string
#         quiz_data = json.loads(file_content)
#         if not quiz_data.get('questions'):  # Check if 'questions' exists
#             raise ValueError("Quiz data must contain 'questions'.")
#         return quiz_data
#     except (json.JSONDecodeError, ValueError) as e:
#         current_app.logger.error(f"Error loading quiz data: {e}")
#         return None
    

# @qagen_bp.route('/', methods=['GET', 'POST'])
# @jwt_required()
# def quiz_input():
#     session.clear()
#     session['user_id'] = 1 
#     session['document_id'] = 1 
#     session['current_question'] = 0
#     session['user_answers'] = {}
#     return redirect(url_for('QAGenerator.quiz'))



@qagen_bp.route('/start_quiz', methods=['POST'])
@jwt_required()
def start_quiz():
    # Clear previous quiz session data
    session.pop('quiz_start_time', None)
    session.pop('user_answers', None)
    session.pop('current_question', None)
    session.pop('quiz_data', None)

    # Get document_id from form data
    document_id = request.form.get('document_id')
    if document_id is None:
        return "Document ID is required", 400

    # Store document_id and set initial question index in the session
    session['current_document_id'] = document_id
    session['current_question'] = 0  # Initialize current_question to 0 for a new quiz attempt

    # Redirect to the main quiz route
    return redirect(url_for('QAGenerator.quiz'))

@qagen_bp.route('/quiz', methods=['GET', 'POST'])
@jwt_required()
def quiz():
    user_id = get_jwt_identity()

    # Get document_id from session or form
    document_id = session.get('current_document_id') or request.form.get('document_id')
    if document_id is None:
        return "Document ID is required", 400

    # Initialize document_id in session if not set
    session['current_document_id'] = document_id

    # Initialize quiz start time if not already set
    if 'quiz_start_time' not in session:
        session['quiz_start_time'] = datetime.utcnow()

    # Fetch questions for the specified document
    questions = db.session.query(Question).filter_by(document_id=document_id).all()
    if not questions:
        return "No questions found for this document", 404

    # Convert questions to a list of dictionaries and store in session if not already done
    if 'quiz_data' not in session:
        quiz_data = {'questions': [question.to_dict() for question in questions]}
        session['quiz_data'] = quiz_data

    # Number of questions and retrieve current question index safely
    quiz_data = session['quiz_data']
    num_questions = len(quiz_data['questions'])
    question_number = session.get('current_question', 0)  # Use get with default 0 to avoid KeyError

    # Get user answers safely from session or initialize if not set
    user_answers = session.get('user_answers', {})

    # Calculate answer status for each question
    answer_status = [("answered" if i in user_answers else "unanswered") for i in range(num_questions)]
    answered_count = len(user_answers)

    if request.method == 'POST':

        
        # Handle navigation buttons: next, back, submit
        if 'question_number' in request.form:
            try:
                goto_question = int(request.form['question_number'])
                if 0 <= goto_question < num_questions:
                    session['current_question'] = goto_question
                    return redirect(url_for('QAGenerator.quiz'))
                else:
                    return "Invalid question number", 400
            except (ValueError, TypeError):
                return "Invalid question number", 400

        # Process user's answer to the current question
        user_answer = request.form.get('question')
        if user_answer:
            user_answers[question_number] = user_answer
            session['user_answers'] = user_answers

        # Navigate based on button clicked
        if 'next' in request.form and question_number + 1 < num_questions:
            session['current_question'] += 1
            return redirect(url_for('QAGenerator.quiz'))
        elif 'back' in request.form and question_number > 0:
            session['current_question'] -= 1
            return redirect(url_for('QAGenerator.quiz'))
        elif 'submit' in request.form:
            return redirect(url_for('QAGenerator.results'))

    # Retrieve the current question details
    current_question = quiz_data['questions'][question_number] if 0 <= question_number < num_questions else None

    return render_template(
        'quiz.html',
        quiz_data=quiz_data,
        current_question=current_question,
        question_number=question_number + 1,
        num_questions=num_questions,
        user_answers=user_answers,
        options=current_question.get('options') if current_question else [],
        answer_status=answer_status,
        answered_count=answered_count,
        document_id=session['current_document_id']
    )



@qagen_bp.route('/results', methods=['GET'])
@jwt_required()
def results():
    user_id = get_jwt_identity()#session.get('user_id')  # Get user ID from the session
    document_id = session.get('current_document_id')  # Get document ID from session
    quiz_start_time = session.get('quiz_start_time')
    if not quiz_start_time:
        quiz_start_time = datetime.utcnow()
        current_app.logger.warning("Quiz start time not found in session. Using current time.")
    quiz_end_time = datetime.utcnow()
    quiz_data = session.get('quiz_data')
    user_answers = session.get('user_answers', {})



    if not quiz_data or not user_answers:  # Check for missing data
        return redirect(url_for('QAGenerator.quiz'))

    questions = [question for question in quiz_data.get('questions', [])]
    num_questions = len(questions)
    score = 0
    results = []
    unanswered_count = num_questions - len(user_answers)

    for i in range(num_questions):
        question_data = questions[i]
        question_id = question_data.get('id') # Get the question ID
        user_answer = user_answers.get(i)
        correct_answer = question_data.get('answer')
        is_correct = (user_answer == correct_answer) if user_answer is not None else False
        if is_correct:
            score += 1
        results.append({'question': question_data.get('question', ''), 'user_answer': user_answer,
                        'correct_answer': correct_answer, 'is_correct': is_correct,
                        'explanation': question_data.get('explanation', '')})

    try:

        quiz_attempt = QuizAttempt(
            participant_id=user_id,
            start_time=quiz_start_time,
            end_time=quiz_end_time,
            total_answered=len(user_answers),
            total_unanswered=unanswered_count,
            score=score
        )
        db.session.add(quiz_attempt)
        db.session.flush()  # Flush to get the attempt_id

        for i in range(num_questions):
            question_data = questions[i]
            question_id = question_data.get('id')
            user_answer = user_answers.get(i)
            if user_answer is not None:
                is_correct = user_answer == question_data.get('answer')
                quiz_response = QuizResponse(
                    attempt_id=quiz_attempt.attempt_id,  # Use attempt_id
                    question_id=question_id,
                    selected_answer=user_answer,
                    is_correct=is_correct,
                )
                db.session.add(quiz_response)


        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Error inserting data: " + str(e))
        return "Error saving results", 500

    #finally:
      #session.clear()


    percentage = (score / num_questions) * 100 if num_questions > 0 else 0
    return render_template('results.html', results=results, score=score, total=num_questions, percentage=percentage)



@qagen_bp.route('/personal_analytics', methods=['GET', 'POST'])
def personal_analytics():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    try:
        quiz_attempts_query = (
            db.session.query(
                QuizAttempt.attempt_id,
                Document.filename,
                QuizAttempt.start_time,
                QuizAttempt.total_answered,
                QuizAttempt.total_unanswered,
                QuizAttempt.score,
                (QuizAttempt.total_answered + QuizAttempt.total_unanswered).label('total_questions')
            )
            .select_from(QuizAttempt)  # Start the join from QuizAttempt
            .join(QuizResponse, QuizAttempt.attempt_id == QuizResponse.attempt_id)
            .join(Question, QuizResponse.question_id == Question.id)
            .join(Document, Question.document_id == Document.id)
            .filter(QuizAttempt.participant_id == user_id)
            .order_by(QuizAttempt.start_time.asc())  # Order attempts by date
            .all()
        )

        # Assign attempt numbers
        quiz_attempts = []
        for idx, row in enumerate(quiz_attempts_query, start=1):
            quiz_attempts.append({
                'attempt_id': row.attempt_id,
                'filename': row.filename,
                'start_time': row.start_time.strftime('%Y-%m-%d %H:%M'),
                'total_answered': row.total_answered,
                'total_unanswered': row.total_unanswered,
                'score': row.score,
                'total_questions': row.total_questions,
                'attempt_number': f"{idx}{'st' if idx == 1 else 'nd' if idx == 2 else 'rd' if idx == 3 else 'th'} attempt"
            })

        # Prepare graph data
        graph_data = [
            {
                'date': attempt['start_time'],  # Use existing 'start_time' string
                'score': attempt['score'],
                'total_questions': attempt['total_questions']
            }
            for attempt in quiz_attempts if 'total_questions' in attempt and 'score' in attempt
        ]

        # Debugging: print the graph_data to console
        current_app.logger.debug(f"Graph Data: {json.dumps(graph_data)}")

    except Exception as e:
        current_app.logger.error(f"Database error fetching analytics: {e}")
        return "Error retrieving analytics", 500

    return render_template('personal_analytics.html', quiz_attempts=quiz_attempts, graph_data=json.dumps(graph_data))



@qagen_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login')) 
 
""" 
if __name__ == '__main__':
    app.run(debug=True) """
