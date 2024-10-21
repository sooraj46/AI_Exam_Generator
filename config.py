import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') 
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') 
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_ACCESS_COOKIE_PATH = '/'
    JWT_COOKIE_CSRF_PROTECT = False  # Enable in production
    JWT_COOKIE_SECURE = False  # Set to True in production (requires HTTPS)
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'
    JWT_COOKIE_SAMESITE = 'Lax'  
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB upload limit
    ALLOWED_EXTENSIONS = {'pdf'}

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    # Additional production configurations

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
