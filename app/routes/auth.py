from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_user, logout_user

from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def login_page():
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        login_user(user)

        if user.is_professor:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.ide', student_uuid=user.uuid))

    return render_template('login.html', error="Invalid credentials. Please try again."), 401


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login_page'))