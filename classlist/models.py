from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from classlist import db


class Teacher(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), default="李老师", nullable=False)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    class_groups = db.relationship(
        "ClassGroup",
        backref="teacher",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClassGroup.name",
    )
    subjects = db.relationship(
        "Subject",
        backref="teacher",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Subject.name",
    )
    grade_rules = db.relationship(
        "GradeRule",
        backref="teacher",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def validate_password(self, password):
        return check_password_hash(self.password_hash, password)


class ClassGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    school_year = db.Column(db.String(20), default="2026", nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    students = db.relationship(
        "Student",
        backref="class_group",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Student.student_number",
    )
    terms = db.relationship(
        "Term",
        backref="class_group",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Term.starts_on.desc()",
    )
    exams = db.relationship(
        "Exam",
        backref="class_group",
        cascade="all, delete-orphan",
        lazy=True,
    )

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "name", name="uq_class_group_teacher_name"),
    )


class Term(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    class_group_id = db.Column(db.Integer, db.ForeignKey("class_group.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    starts_on = db.Column(db.Date, default=date.today, nullable=False)
    ends_on = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    teacher = db.relationship("Teacher", backref=db.backref("terms", lazy=True))
    exams = db.relationship(
        "Exam",
        backref="term",
        cascade="all, delete-orphan",
        lazy=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "class_group_id",
            "name",
            name="uq_term_teacher_class_name",
        ),
    )


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    color = db.Column(db.String(20), default="#C96442", nullable=False)

    exams = db.relationship(
        "Exam",
        backref="subject",
        cascade="all, delete-orphan",
        lazy=True,
    )

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "name", name="uq_subject_teacher_name"),
    )


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    class_group_id = db.Column(db.Integer, db.ForeignKey("class_group.id"), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    student_number = db.Column(db.String(30), nullable=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    teacher = db.relationship("Teacher", backref=db.backref("students", lazy=True))
    scores = db.relationship(
        "Score",
        backref="student",
        cascade="all, delete-orphan",
        lazy=True,
    )
    notes = db.relationship(
        "TeacherNote",
        backref="student",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="TeacherNote.note_date.desc()",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "class_group_id",
            "name",
            name="uq_student_teacher_class_name",
        ),
    )


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    class_group_id = db.Column(db.Integer, db.ForeignKey("class_group.id"), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey("term.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    exam_type = db.Column(db.String(30), default="单元测试", nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    full_score = db.Column(db.Integer, default=100, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    teacher = db.relationship("Teacher", backref=db.backref("exams", lazy=True))
    scores = db.relationship(
        "Score",
        backref="exam",
        cascade="all, delete-orphan",
        lazy=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "class_group_id",
            "term_id",
            "subject_id",
            "title",
            name="uq_exam_context_title",
        ),
    )


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    score = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    remark = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    teacher = db.relationship("Teacher", backref=db.backref("scores", lazy=True))

    __table_args__ = (
        db.UniqueConstraint("exam_id", "student_id", name="uq_score_exam_student"),
    )


class TeacherNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    note_date = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    teacher = db.relationship("Teacher", backref=db.backref("notes", lazy=True))


class GradeRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    name = db.Column(db.String(40), default="默认等级规则", nullable=False)
    excellent_min = db.Column(db.Integer, default=90, nullable=False)
    pass_min = db.Column(db.Integer, default=60, nullable=False)
