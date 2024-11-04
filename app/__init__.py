import os
from flask import Flask
from flask_session import Session
from app.routes.QAGenerator import qagen_bp
from app.routes.generateexam import examgenerator_bp
from .models import db, bcrypt, User
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.conductor import conductor_bp
from config import config
import json
#from flask_wtf.csrf import CSRFProtect

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate = Migrate(app, db)
    jwt = JWTManager(app)

    #session 
     
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    Session(app)
    app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB

    #csrf = CSRFProtect(app)


    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Register the json_loads filter
    @app.template_filter('json_loads')
    def json_loads_filter(s):
        return json.loads(s)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(conductor_bp, url_prefix='/conductor')
    app.register_blueprint(qagen_bp, url_prefix='/quiz')
    app.register_blueprint(examgenerator_bp, url_prefix='/examgenerator') 

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