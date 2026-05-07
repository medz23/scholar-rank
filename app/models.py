import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Text, Boolean, ForeignKey, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    global_bonus: Mapped[float] = mapped_column(Float, default=0.0)

class UserProblem(db.Model):
    __tablename__ = 'user_problem'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)
    problem_id: Mapped[int] = mapped_column(ForeignKey('problem.id'), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default='pending')
    submitted_code: Mapped[str] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="user_problems")
    problem: Mapped["Problem"] = relationship(back_populates="user_problems")

    test_results: Mapped[list["UserTestResult"]] = relationship(
        back_populates="user_problem", cascade="all, delete-orphan"
    )

    @property
    def problem_score(self) -> float:
        score = 0.0
        for result in self.test_results:
            if result.passed:
                score += result.test_case.weight
        return score


class UserTestResult(db.Model):
    __tablename__ = 'user_test_result'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_problem_id: Mapped[int] = mapped_column(ForeignKey('user_problem.id'), nullable=False)
    test_case_id: Mapped[int] = mapped_column(ForeignKey('test_case.id'), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)

    user_problem: Mapped["UserProblem"] = relationship(back_populates="test_results")
    test_case: Mapped["TestCase"] = relationship()


class Group(db.Model):
    __tablename__ = 'group'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    students: Mapped[list["User"]] = relationship(back_populates="group", cascade="all, delete-orphan")

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)

    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_professor: Mapped[bool] = mapped_column(Boolean, default=False)
    strikes: Mapped[int] = mapped_column(Integer, default=0)

    group_id: Mapped[int] = mapped_column(ForeignKey('group.id'), nullable=True)
    group: Mapped["Group"] = relationship(back_populates="students")

    user_problems: Mapped[list["UserProblem"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def final_grade(self) -> float:
        if self.is_professor:
            return 0.0

        earned = 0.0
        max_possible = 0.0

        for up in self.user_problems:
            max_possible += up.problem.weight
            earned += up.problem_score

        settings = SystemSettings.query.first()
        bonus = settings.global_bonus if settings else 0.0

        if max_possible <= 0:
            return round(bonus, 2)

        grade = (earned / max_possible) * (10 - bonus) + bonus
        return round(min(grade, 10.0), 2)


class Problem(db.Model):
    __tablename__ = 'problem'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    exam_order: Mapped[int] = mapped_column(Integer, default=1)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    start_code: Mapped[str] = mapped_column(Text, nullable=True, default="# Write your solution here\n")
    function_name: Mapped[str] = mapped_column(String(120), nullable=True, default=None)
    weight: Mapped[float] = mapped_column(Float, default=100.0)

    user_problems: Mapped[list["UserProblem"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    test_cases: Mapped[list["TestCase"]] = relationship(
        back_populates="parent_problem", cascade="all, delete-orphan"
    )

class TestCase(db.Model):
    __tablename__ = 'test_case'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey('problem.id'), nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    parent_problem: Mapped["Problem"] = relationship(back_populates="test_cases")