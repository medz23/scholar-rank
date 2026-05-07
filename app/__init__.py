import os
import secrets
import time

from flask import Flask
from flask_login import LoginManager

from app.models import db, User, Problem, TestCase
from app.routes.group import group_bp

ADMIN_UUID = os.environ.get('ADMIN_URL_SECRET', 'd9e84b2c-7f31-4a9b-90c2-1a2b3c4d5e6f')


def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 14400  # 4 hours

    db_url = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if 'postgresql' in db_url:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 20,
            'max_overflow': 10,
            'pool_pre_ping': True,
        }
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'check_same_thread': False},
        }

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login_page'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/pclp/login')
    app.register_blueprint(student_bp, url_prefix='/pclp/student')
    app.register_blueprint(admin_bp, url_prefix=f'/pclp/admin-{ADMIN_UUID}')
    app.register_blueprint(group_bp, url_prefix=f'/pclp/group-{ADMIN_UUID}')

    with app.app_context():
        _wait_for_db(db, max_retries=15, delay=2)

        db.create_all()

        prof_user = os.environ.get('PROFESSOR_USERNAME', 'profesor')
        prof_pass = os.environ.get('PROFESSOR_PASSWORD', 'password')

        if not User.query.filter_by(username=prof_user).first():
            prof = User(username=prof_user, is_professor=True)
            prof.set_password(prof_pass)
            db.session.add(prof)
            db.session.commit()

    return app


def _wait_for_db(db, max_retries=15, delay=2):
    for attempt in range(1, max_retries + 1):
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("SELECT 1"))
            print(f"[INIT] Database connected on attempt {attempt}.")
            return
        except Exception as e:
            if attempt == max_retries:
                print(f"[INIT] Database not available after {max_retries} attempts. Giving up.")
                raise
            print(f"[INIT] Database not ready (attempt {attempt}/{max_retries}): {e}")
            time.sleep(delay)