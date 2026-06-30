from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from classlist import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), default="Admin")
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def validate_password(self, password):
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    courses = db.relationship(
        "StudentCourse",
        backref="student",
        cascade="all, delete-orphan",
        lazy=True,
    )


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    students = db.relationship(
        "StudentCourse",
        backref="course",
        cascade="all, delete-orphan",
        lazy=True,
    )


class StudentCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
