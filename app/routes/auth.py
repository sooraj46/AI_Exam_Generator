from flask import Blueprint, request, render_template, redirect, url_for, flash
from ..models import db, User, Role
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies
from datetime import timedelta

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('User already exists', 'danger')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email)
        user.set_password(password)

        # Assign default role
        exam_taker_role = Role.query.filter_by(name='ExamTaker').first()
        if exam_taker_role:
            user.roles.append(exam_taker_role)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        username_or_email = data.get('username_or_email')
        password = data.get('password')

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and user.check_password(password):
            access_token = create_access_token(identity=user.id, expires_delta=timedelta(hours=1))
            response = redirect(url_for('admin.manage_users') if user.has_role('Administrator') else
                                url_for('conductor.manage_groups') if user.has_role('ExamConductor') else
                                url_for('examgenerator.upload_and_generate') if user.has_role('ExamTaker') else
                                url_for('auth.login'))
            set_access_cookies(response, access_token)
            flash('Logged in successfully.', 'success')
            return response
        else:
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth_bp.route('/logout', methods=['GET'])
def logout():
    response = redirect(url_for('auth.login'))
    unset_jwt_cookies(response)
    flash('Logged out successfully.', 'success')
    return response
