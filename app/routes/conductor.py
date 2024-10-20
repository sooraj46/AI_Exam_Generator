from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import db, User, Group
from ..utils.decorators import roles_required

conductor_bp = Blueprint('conductor', __name__, template_folder='../templates/conductor')

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
