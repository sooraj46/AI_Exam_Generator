from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
import json

db = SQLAlchemy()
bcrypt = Bcrypt()

# Association tables for many-to-many relationships
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

group_users = db.Table('group_users',
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    questions = db.relationship('Question', backref='exam', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    access_code = db.Column(db.String(50), unique=True, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    group = db.relationship('Group', backref='exams')
    time_limit = db.Column(db.Integer, nullable=False)  # Time limit in minutes

class ExamResponse(db.Model):
    __tablename__ = 'exam_responses'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    responses = db.Column(db.Text)  # JSON string of user responses
    score = db.Column(db.Float)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    # Relationships
    user = db.relationship('User', backref='exam_responses')
    exam = db.relationship('Exam', backref='exam_responses')

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    questions = db.relationship('Question', backref='document', lazy=True)
    owner = db.relationship('User', backref='documents')

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)  # Stores options as JSON
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=True)
    def to_dict(self):
        options_data = self.options
        if isinstance(options_data, str): # Check if it's a string
            options_data = json.loads(options_data) # Parse only if it is.

        return {
            'id': self.id,
            'question': self.question_text,
            'options': options_data, # Use options_data
            'answer': self.correct_answer,
            'explanation': self.explanation
        }
    

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))

    def __repr__(self):
        return f"<Role {self.name}>"

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))
    groups = db.relationship('Group', secondary=group_users, backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        return any(role.name == role_name for role in self.roles)

    def __repr__(self):
        return f"<User {self.username}>"

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    access = db.Column(db.Boolean, default=True)  # Indicates if group has access

    created_by_user = db.relationship('User', backref='created_groups')

    def __repr__(self):
        return f"<Group {self.name}>"
    
class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    attempt_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    total_answered = db.Column(db.Integer)
    total_unanswered = db.Column(db.Integer)
    score = db.Column(db.Integer)

    participant = db.relationship('User', backref='quiz_attempts')  # Relationship with User model
    responses = db.relationship('QuizResponse', backref='attempt', lazy=True) # Relationship to responses


class QuizResponse(db.Model):
    __tablename__ = 'quiz_responses'
    response_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.attempt_id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean)

    question = db.relationship('Question', backref='responses') # Add relationship

    def __repr__(self):
        return f"<Group {self.name}>"
    