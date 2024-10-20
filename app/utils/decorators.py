from functools import wraps
from flask import flash, redirect, url_for
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from ..models import User

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                user = User.query.get(user_id)
                if not user:
                    flash('User not found.', 'danger')
                    return redirect(url_for('auth.login'))
                user_roles = [role.name for role in user.roles]
                if any(role in user_roles for role in roles):
                    return fn(*args, **kwargs)
                else:
                    flash('Access denied.', 'danger')
                    return redirect(url_for('auth.login'))
            except:
                flash('Authentication required.', 'danger')
                return redirect(url_for('auth.login'))
        return wrapper
    return decorator
