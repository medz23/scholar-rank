import csv
from io import StringIO

from flask import Blueprint, render_template, request, redirect, url_for, Response
from flask_login import current_user

from app.models import db, User, Problem, Group, UserProblem

group_bp = Blueprint('group', __name__)


@group_bp.before_request
def require_admin():
    if not current_user.is_authenticated or not current_user.is_professor:
        return redirect(url_for('auth.login_page'))


@group_bp.route('/add', methods=['POST'])
def add_group():
    name = request.form.get('name')
    if name:
        db.session.add(Group(name=name))
        db.session.commit()
    return redirect(url_for('admin.dashboard'))


@group_bp.route('/delete/<int:group_id>', methods=['POST'])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('admin.dashboard'))


@group_bp.route('/<int:group_id>')
def group_page(group_id):
    group = Group.query.get_or_404(group_id)
    problems = Problem.query.all()
    return render_template('group.html', group=group, problems=problems)


@group_bp.route('/<int:group_id>/add_student', methods=['POST'])
def add_student(group_id):
    username = request.form.get('username')
    password = request.form.get('password')

    if not User.query.filter_by(username=username).first():
        new_student = User(username=username, group_id=group_id)
        new_student.set_password(password)
        db.session.add(new_student)
        db.session.commit()

    return redirect(url_for('group.group_page', group_id=group_id))


@group_bp.route('/<int:group_id>/export_csv')
def export_group_csv(group_id):
    group = Group.query.get_or_404(group_id)
    problems = Problem.query.order_by(Problem.exam_order).all()

    si = StringIO()
    cw = csv.writer(si)

    headers = ['Username', 'Strikes', 'Final Score']
    for p in problems:
        headers.extend([f'Prob {p.id} Score', f'Prob {p.id} Code'])
    cw.writerow(headers)

    for student in group.students:
        row = [student.username, student.strikes]
        prob_cols = []

        for p in problems:
            up = UserProblem.query.filter_by(user_id=student.id, problem_id=p.id).first()
            if up:
                score = up.problem_score
                code = up.submitted_code or "No Submission"
                prob_cols.extend([score, code])
            else:
                prob_cols.extend([0, "Not Assigned"])

        row.append(student.final_grade)
        row.extend(prob_cols)
        cw.writerow(row)

    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = f"attachment; filename=group_{group.name}_results.csv"
    return output


@group_bp.route('/<int:group_id>/assign_problem_to_group', methods=['POST'])
def assign_problem_to_group(group_id):
    group = Group.query.get_or_404(group_id)
    problem_id = request.form.get('problem_id')

    if problem_id:
        for student in group.students:
            existing_assignment = UserProblem.query.filter_by(user_id=student.id, problem_id=problem_id).first()

            if not existing_assignment:
                new_assignment = UserProblem(
                    user_id=student.id,
                    problem_id=problem_id,
                    status='pending'
                )
                db.session.add(new_assignment)

        db.session.commit()

    return redirect(url_for('group.group_page', group_id=group_id))