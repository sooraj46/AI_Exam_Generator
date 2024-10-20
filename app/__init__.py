from flask import Flask
from .models import db, bcrypt, User
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.conductor import conductor_bp
from config import config

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate = Migrate(app, db)
    jwt = JWTManager(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(conductor_bp, url_prefix='/conductor')

    # Context processor to inject current_user into templates
    @app.context_processor
    def inject_user():
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = db.session.query(User).get(user_id)
            return dict(current_user=user)
        except:
            return dict(current_user=None)

    return app
