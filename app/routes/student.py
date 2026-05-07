import random

from flask import Blueprint, render_template, request, jsonify, abort
from flask import redirect, url_for
from flask_login import current_user

from app.models import db, Problem, UserProblem, UserTestResult
from app.services.executor import run_tests

student_bp = Blueprint('student', __name__)


@student_bp.before_request
def require_student():
    if not current_user.is_authenticated:
        if request.is_json:
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for('auth.login_page'))


@student_bp.route('/student-<student_uuid>/')
def ide(student_uuid):
    if current_user.is_professor:
        return redirect(url_for('admin.dashboard'))

    user = current_user

    if user.uuid != student_uuid:
        abort(403)

    if not user.user_problems:
        all_problems = Problem.query.all()
        if all_problems:
            grouped_problems = {}
            for p in all_problems:
                grouped_problems.setdefault(p.exam_order, []).append(p)

            for order, probs in grouped_problems.items():
                random_prob = random.choice(probs)
                assignment = UserProblem(user=user, problem=random_prob, status='pending')
                db.session.add(assignment)
            db.session.commit()

    user_problem = UserProblem.query.join(Problem).filter(
        UserProblem.user_id == user.id,
        UserProblem.status == 'pending'
    ).order_by(Problem.exam_order).first()

    total_assigned = len(user.user_problems)
    completed_assigned = len([up for up in user.user_problems if up.status == 'completed'])

    problem = user_problem.problem if user_problem else None

    if not problem and total_assigned > 0:
        return render_template('exam_complete.html', user=user)

    return render_template('student.html', problem=problem, current_num=completed_assigned + 1, total=total_assigned)


@student_bp.route('/run', methods=['POST'])
def run_code():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    problem_id = data.get('problem_id')
    code = data.get('code')

    if not problem_id or code is None:
        return jsonify({"error": "Missing problem_id or code"}), 400

    problem = Problem.query.get(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    if not current_user.is_professor:
        user_problem = UserProblem.query.filter_by(
            user_id=current_user.id, problem_id=problem_id
        ).first()
        if not user_problem:
            return jsonify({"error": "Problem not assigned to you"}), 403
        if user_problem.status == 'completed':
            return jsonify({"error": "Already submitted"}), 403

    if not problem.test_cases:
        return jsonify({"test_results": [], "error": "No test cases defined for this problem"})

    try:
        results = run_tests(code, problem.test_cases, function_name=problem.function_name)
        return jsonify({"test_results": results})
    except Exception as e:
        return jsonify({"error": f"Execution failed: {str(e)[:300]}"}), 500


@student_bp.route('/submit', methods=['POST'])
def submit():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    code = data.get('code')
    problem_id = data.get('problem_id')

    if not problem_id or code is None:
        return jsonify({"error": "Missing problem_id or code"}), 400

    user_id = current_user.id

    problem = Problem.query.get(problem_id)
    if not problem:
        return jsonify({"error": "Problem not found"}), 404

    user_problem = UserProblem.query.filter_by(user_id=user_id, problem_id=problem_id).first()
    if not user_problem:
        return jsonify({"error": "Problem not assigned to you"}), 403

    if user_problem.status == 'completed':
        return jsonify({"error": "Already submitted", "redirect_url": url_for('student.results', problem_id=problem_id)})

    try:
        results = run_tests(code, problem.test_cases, function_name=problem.function_name)
    except Exception as e:
        return jsonify({"error": f"Execution failed: {str(e)[:300]}"}), 500

    user_problem.status = 'completed'
    user_problem.submitted_code = code
    UserTestResult.query.filter_by(user_problem_id=user_problem.id).delete()
    for res in results:
        test_result = UserTestResult(
            user_problem_id=user_problem.id,
            test_case_id=res['test_id'],
            passed=res['passed']
        )
        db.session.add(test_result)
    db.session.commit()

    return jsonify({"redirect_url": url_for('student.results', problem_id=problem_id)})


@student_bp.route('/results/<int:problem_id>')
def results(problem_id):
    user = current_user
    user_problem = UserProblem.query.filter_by(user_id=user.id, problem_id=problem_id).first()

    if not user_problem or user_problem.status != 'completed':
        return redirect(url_for('student.ide', student_uuid=user.uuid))

    more_pending = UserProblem.query.filter_by(user_id=user.id, status='pending').count() > 0

    return render_template('results.html', user_problem=user_problem, more_pending=more_pending, user=user)


@student_bp.route('/log_strike', methods=['POST'])
def log_strike():
    user = current_user
    if user.strikes >= 3:
        return jsonify({"strikes": user.strikes})
    user.strikes += 1
    db.session.commit()

    return jsonify({"strikes": user.strikes})


@student_bp.route('/get_strikes')
def get_strikes():
    return jsonify({"strikes": current_user.strikes})