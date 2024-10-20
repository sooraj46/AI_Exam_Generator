import bcrypt
from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, User, Group, Role
from ..utils.decorators import roles_required

conductor_bp = Blueprint('conductor', __name__, template_folder='../templates/conductor')

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

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        exam_taker_role = Role.query.filter_by(name='ExamTaker').first()

        if not exam_taker_role:
            flash('Exam Taker role not found.', 'danger')
            return redirect(url_for('conductor.manage_exam_takers'))

        new_exam_taker = User(username=username, email=email, password=hashed_password)
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
