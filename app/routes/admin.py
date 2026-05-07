from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user

from app.models import db, User, Problem, Group, UserProblem, SystemSettings, TestCase

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
def require_admin():
    if not current_user.is_authenticated or not current_user.is_professor:
        return redirect(url_for('auth.login_page'))


@admin_bp.route('/')
def dashboard():
    problems = Problem.query.all()
    groups = Group.query.all()

    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings(global_bonus=0.0)
        db.session.add(settings)
        db.session.commit()

    return render_template('admin.html', groups=groups, problems=problems, settings=settings)


@admin_bp.route('/update_global_bonus', methods=['POST'])
def update_global_bonus():
    settings = SystemSettings.query.first()
    settings.global_bonus = request.form.get('global_bonus', type=float, default=0.0)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/group/<int:group_id>/add_student', methods=['POST'])
def add_student(group_id):
    username = request.form.get('username')
    password = request.form.get('password')
    if not User.query.filter_by(username=username).first():
        new_student = User(username=username, group_id=group_id)
        new_student.set_password(password)
        db.session.add(new_student)
        db.session.commit()
    return redirect(url_for('group.group_page', group_id=group_id))


@admin_bp.route('/edit_student/<int:student_id>', methods=['POST'])
def edit_student(student_id):
    student = User.query.get_or_404(student_id)
    new_password = request.form.get('password')
    if new_password:
        student.set_password(new_password)
        db.session.commit()
    if student.group_id:
        return redirect(url_for('group.group_page', group_id=student.group_id))
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    student = User.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/assign_problem/<int:student_id>', methods=['POST'])
def assign_problem(student_id):
    student = User.query.get_or_404(student_id)
    problem_id = request.form.get('problem_id')

    if problem_id:
        problem = Problem.query.get(problem_id)
        existing = UserProblem.query.filter_by(user_id=student.id, problem_id=problem.id).first()
        if not existing:
            new_assignment = UserProblem(user=student, problem=problem)
            db.session.add(new_assignment)
            db.session.commit()

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/add_problem', methods=['POST'])
def add_problem():
    title = request.form.get('title')
    description = request.form.get('description')
    exam_order = request.form.get('exam_order', type=int, default=1)
    start_code = request.form.get('start_code')
    function_name = request.form.get('function_name') or None
    weight = request.form.get('weight', type=float, default=100.0)

    prob = Problem(
        title=title,
        description=description,
        exam_order=exam_order,
        start_code=start_code,
        function_name=function_name,
        weight=weight
    )
    db.session.add(prob)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/edit_problem/<int:problem_id>', methods=['POST'])
def edit_problem(problem_id):
    prob = Problem.query.get_or_404(problem_id)
    prob.title = request.form.get('title')
    prob.description = request.form.get('description')
    prob.exam_order = request.form.get('exam_order', type=int, default=1)
    prob.start_code = request.form.get('start_code')
    prob.function_name = request.form.get('function_name') or None
    prob.weight = request.form.get('weight', type=float, default=100.0)

    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/delete_problem/<int:problem_id>', methods=['POST'])
def delete_problem(problem_id):
    prob = Problem.query.get_or_404(problem_id)
    db.session.delete(prob)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/add_test/<int:problem_id>', methods=['POST'])
def add_test(problem_id):
    input_data = request.form.get('input_data')
    expected_output = request.form.get('expected_output')
    weight = request.form.get('weight', type=float, default=0.0)
    is_hidden = request.form.get('is_hidden') == 'on'
    test_case = TestCase(problem_id=problem_id, input_data=input_data,
                         expected_output=expected_output, weight=weight, is_hidden=is_hidden)
    db.session.add(test_case)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/delete_test/<int:test_id>', methods=['POST'])
def delete_test(test_id):
    test_case = TestCase.query.get_or_404(test_id)
    db.session.delete(test_case)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))