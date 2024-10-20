from flask import Blueprint, request, render_template, flash, redirect, url_for
from flask_jwt_extended import jwt_required
from ..models import db, User, Role
from ..utils.decorators import roles_required

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')

@admin_bp.route('/manage-users', methods=['GET', 'POST'])
@jwt_required()
@roles_required('Administrator')
def manage_users():
    if request.method == 'POST':
        # Handle user creation
        data = request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role_name = data.get('role')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('User already exists.', 'danger')
            return redirect(url_for('admin.manage_users'))

        user = User(username=username, email=email)
        user.set_password(password)

        role = Role.query.filter_by(name=role_name).first()
        if role:
            user.roles.append(role)

        db.session.add(user)
        db.session.commit()

        flash('User added successfully.', 'success')
        return redirect(url_for('admin.manage_users'))

    users = User.query.all()
    roles = Role.query.all()
    return render_template('manage_users.html', users=users, roles=roles)

@admin_bp.route('/assign-role', methods=['POST'])
@jwt_required()
@roles_required('Administrator')
def assign_role():
    data = request.form
    user_id = data.get('user_id')
    role_name = data.get('role')

    user = User.query.get(user_id)
    role = Role.query.filter_by(name=role_name).first()

    if user and role:
        if role not in user.roles:
            user.roles.append(role)
            db.session.commit()
            flash('Role assigned successfully.', 'success')
        else:
            flash('User already has this role.', 'warning')
        return redirect(url_for('admin.manage_users'))
    else:
        flash('User or Role not found.', 'danger')
        return redirect(url_for('admin.manage_users'))
