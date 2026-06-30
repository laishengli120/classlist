from datetime import date

import click
from sqlalchemy import inspect, text

from classlist import app, db
from classlist.models import (
    ClassGroup,
    Exam,
    GradeRule,
    Score,
    Student,
    Subject,
    Teacher,
    TeacherNote,
    Term,
)


def drop_database_tables():
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if not table_names:
        return
    preparer = db.engine.dialect.identifier_preparer
    with db.engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        for table_name in table_names:
            connection.execute(text(f"DROP TABLE IF EXISTS {preparer.quote(table_name)}"))
        connection.execute(text("PRAGMA foreign_keys=ON"))


def seed_default_data():
    if Teacher.query.filter_by(username="admin").first():
        return False

    teacher = Teacher(username="admin", name="李老师")
    teacher.set_password("admin")
    db.session.add(teacher)
    db.session.flush()

    class_group = ClassGroup(
        teacher_id=teacher.id,
        name="四年级 2 班",
        school_year="2026",
    )
    db.session.add(class_group)
    db.session.flush()

    term = Term(
        teacher_id=teacher.id,
        class_group_id=class_group.id,
        name="2026 年春季学期",
        starts_on=date(2026, 2, 16),
        ends_on=date(2026, 7, 10),
        is_active=True,
    )
    db.session.add(term)

    subjects = [
        Subject(teacher_id=teacher.id, name="数学", color="#C96442"),
        Subject(teacher_id=teacher.id, name="语文", color="#627789"),
        Subject(teacher_id=teacher.id, name="英语", color="#5F7D68"),
    ]
    db.session.add_all(subjects)
    db.session.flush()

    students = [
        ("20260401", "王明"),
        ("20260402", "李华"),
        ("20260403", "张然"),
        ("20260404", "陈思"),
        ("20260405", "赵一诺"),
        ("20260406", "刘宇"),
        ("20260407", "周涵"),
        ("20260408", "孙悦"),
        ("20260409", "吴桐"),
        ("20260410", "郑佳"),
        ("20260411", "林可"),
        ("20260412", "何雨"),
    ]
    student_models = [
        Student(
            teacher_id=teacher.id,
            class_group_id=class_group.id,
            student_number=student_number,
            name=name,
        )
        for student_number, name in students
    ]
    db.session.add_all(student_models)
    db.session.flush()

    math = subjects[0]
    exams = [
        Exam(
            teacher_id=teacher.id,
            class_group_id=class_group.id,
            term_id=term.id,
            subject_id=math.id,
            title="数学第三单元测试",
            exam_type="单元测试",
            exam_date=date(2026, 5, 18),
            full_score=100,
        ),
        Exam(
            teacher_id=teacher.id,
            class_group_id=class_group.id,
            term_id=term.id,
            subject_id=math.id,
            title="数学第四单元测试",
            exam_type="单元测试",
            exam_date=date(2026, 6, 5),
            full_score=100,
        ),
        Exam(
            teacher_id=teacher.id,
            class_group_id=class_group.id,
            term_id=term.id,
            subject_id=math.id,
            title="数学第五单元测试",
            exam_type="单元测试",
            exam_date=date(2026, 6, 26),
            full_score=100,
        ),
    ]
    db.session.add_all(exams)
    db.session.flush()

    score_sets = [
        [82, 76, 91, 88, 96, 74, 83, 89, 78, 92, 67, 85],
        [85, 82, 89, 90, 98, 70, 86, 91, 81, 94, 72, 87],
        [92, "sick", 93, 86, 97, None, 88, 84, 63, 95, 75, 90],
    ]
    for exam, scores in zip(exams, score_sets):
        for student, score_value in zip(student_models, scores):
            if score_value == "sick":
                db.session.add(
                    Score(
                        teacher_id=teacher.id,
                        exam_id=exam.id,
                        student_id=student.id,
                        status="sick",
                        remark="病假，待补测",
                    )
                )
                continue
            if score_value is None:
                db.session.add(
                    Score(
                        teacher_id=teacher.id,
                        exam_id=exam.id,
                        student_id=student.id,
                        status="pending",
                    )
                )
                continue
            db.session.add(
                Score(
                    teacher_id=teacher.id,
                    exam_id=exam.id,
                    student_id=student.id,
                    score=score_value,
                    status="scored",
                )
            )

    db.session.add(
        TeacherNote(
            teacher_id=teacher.id,
            student_id=student_models[0].id,
            note_date=date(2026, 6, 18),
            content="课堂回答积极，应用题步骤表达比上月更完整。",
        )
    )
    db.session.add(GradeRule(teacher_id=teacher.id))
    db.session.commit()
    return True


@app.cli.command()
@click.option("--drop", is_flag=True, help="Drop existing tables before creating them.")
def initdb(drop):
    if drop:
        drop_database_tables()
    db.create_all()
    seeded = seed_default_data()
    click.echo("Initialized database.")
    if seeded:
        click.echo("Seeded demo data. Login with username admin and password admin.")


@app.cli.command()
@click.option("--username", prompt=True, help="The username used to log in.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="The password used to log in.",
)
@click.option("--name", default="李老师", help="Display name for the teacher.")
def admin(username, password, name):
    db.create_all()
    teacher = Teacher.query.filter_by(username=username).first()
    if teacher is None:
        teacher = Teacher(username=username, name=name)
        db.session.add(teacher)
    else:
        teacher.name = name
    teacher.set_password(password)
    db.session.commit()
    click.echo("Teacher account saved.")
