import csv
import math
from datetime import date, datetime
from io import StringIO
from types import SimpleNamespace

from flask import Response, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import and_, func, or_

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


STATUS_LABELS = {
    "pending": "未录入",
    "scored": "已录入",
    "absent": "缺考",
    "sick": "病假",
    "exempt": "免考",
}
STATUS_SHORT = {
    "pending": "",
    "scored": "",
    "absent": "缺",
    "sick": "病",
    "exempt": "免",
}
STATUS_ALIASES = {
    "缺": "absent",
    "缺考": "absent",
    "病": "sick",
    "病假": "sick",
    "免": "exempt",
    "免考": "exempt",
}


def parse_date(value, default=None):
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def choose_item(items, session_key, arg_name, prefer_active=False):
    selected_id = request.args.get(arg_name, type=int) or session.get(session_key)
    selected = next((item for item in items if item.id == selected_id), None)
    if selected is None and prefer_active:
        selected = next((item for item in items if getattr(item, "is_active", False)), None)
    if selected is None and items:
        selected = items[0]
    if selected is not None:
        session[session_key] = selected.id
    else:
        session.pop(session_key, None)
    return selected


def get_workspace():
    if not current_user.is_authenticated:
        return SimpleNamespace(
            class_groups=[],
            class_group=None,
            terms=[],
            term=None,
            subjects=[],
            subject=None,
            latest_exam=None,
        )

    class_groups = (
        ClassGroup.query.filter_by(teacher_id=current_user.id, archived=False)
        .order_by(ClassGroup.name.asc())
        .all()
    )
    class_group = choose_item(class_groups, "class_group_id", "class_id")

    terms = []
    term = None
    if class_group is not None:
        terms = (
            Term.query.filter_by(
                teacher_id=current_user.id,
                class_group_id=class_group.id,
            )
            .order_by(Term.is_active.desc(), Term.starts_on.desc())
            .all()
        )
        term = choose_item(terms, "term_id", "term_id", prefer_active=True)

    subjects = (
        Subject.query.filter_by(teacher_id=current_user.id)
        .order_by(Subject.name.asc())
        .all()
    )
    subject = choose_item(subjects, "subject_id", "subject_id")

    latest_exam = None
    if class_group is not None and term is not None:
        latest_query = Exam.query.filter_by(
            teacher_id=current_user.id,
            class_group_id=class_group.id,
            term_id=term.id,
        )
        if subject is not None:
            latest_query = latest_query.filter_by(subject_id=subject.id)
        latest_exam = latest_query.order_by(Exam.exam_date.desc(), Exam.id.desc()).first()

    return SimpleNamespace(
        class_groups=class_groups,
        class_group=class_group,
        terms=terms,
        term=term,
        subjects=subjects,
        subject=subject,
        latest_exam=latest_exam,
    )


@app.context_processor
def inject_workspace():
    workspace = get_workspace()
    return {
        "workspace": workspace,
        "status_labels": STATUS_LABELS,
        "entry_exam": workspace.latest_exam,
    }


def object_for_teacher_or_404(model, object_id):
    return model.query.filter_by(id=object_id, teacher_id=current_user.id).first_or_404()


def default_grade_rule():
    rule = GradeRule.query.filter_by(teacher_id=current_user.id).first()
    if rule is not None:
        return rule
    return SimpleNamespace(excellent_min=90, pass_min=60)


def score_percent(score_value, full_score):
    if score_value is None or not full_score:
        return None
    return score_value / full_score * 100


def grade_for_score(score_value, full_score=100):
    percent = score_percent(score_value, full_score)
    if percent is None:
        return "—"
    rule = default_grade_rule()
    if percent >= rule.excellent_min:
        return "优秀"
    if percent >= 80:
        return "良好"
    if percent >= rule.pass_min:
        return "及格"
    return "待提高"


def format_number(value, suffix=""):
    if value is None:
        return "—"
    if isinstance(value, float):
        value = round(value, 1)
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def format_change(value):
    if value is None:
        return "—"
    if value > 0:
        return f"+{value:g}"
    return f"{value:g}"


def normalize_score_input(raw_value, full_score):
    value = (raw_value or "").strip()
    if value == "":
        return "pending", None
    if value in STATUS_ALIASES:
        return STATUS_ALIASES[value], None
    try:
        score_value = int(value)
    except ValueError as exc:
        raise ValueError("请输入 0 到满分之间的整数，或输入 缺、病、免。") from exc
    if score_value < 0 or score_value > full_score:
        raise ValueError(f"分数必须在 0-{full_score} 之间。")
    return "scored", score_value


def score_display(score):
    if score is None:
        return ""
    if score.status == "scored":
        return "" if score.score is None else str(score.score)
    return STATUS_SHORT.get(score.status, "")


def score_status_label(score):
    if score is None:
        return STATUS_LABELS["pending"]
    return STATUS_LABELS.get(score.status, STATUS_LABELS["pending"])


def score_query_for_exam(exam):
    return Score.query.filter_by(teacher_id=current_user.id, exam_id=exam.id)


def students_for_class(class_group):
    if class_group is None:
        return []
    return (
        Student.query.filter_by(
            teacher_id=current_user.id,
            class_group_id=class_group.id,
            archived=False,
        )
        .order_by(Student.student_number.asc(), Student.id.asc())
        .all()
    )


def previous_score(student_id, exam):
    return (
        Score.query.join(Exam)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student_id,
            Score.status == "scored",
            Score.score.isnot(None),
            Exam.class_group_id == exam.class_group_id,
            Exam.subject_id == exam.subject_id,
            or_(
                Exam.exam_date < exam.exam_date,
                and_(Exam.exam_date == exam.exam_date, Exam.id < exam.id),
            ),
        )
        .order_by(Exam.exam_date.desc(), Exam.id.desc())
        .first()
    )


def score_change(score, exam):
    if score is None or score.status != "scored" or score.score is None:
        return None
    previous = previous_score(score.student_id, exam)
    if previous is None or previous.score is None:
        return None
    return score.score - previous.score


def recent_scores(student_id, class_group_id=None, term_id=None, subject_id=None, limit=4):
    query = (
        db.session.query(Score, Exam)
        .join(Exam, Score.exam_id == Exam.id)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student_id,
            Score.status == "scored",
            Score.score.isnot(None),
        )
    )
    if class_group_id is not None:
        query = query.filter(Exam.class_group_id == class_group_id)
    if term_id is not None:
        query = query.filter(Exam.term_id == term_id)
    if subject_id is not None:
        query = query.filter(Exam.subject_id == subject_id)
    rows = query.order_by(Exam.exam_date.desc(), Exam.id.desc()).limit(limit).all()
    return [
        {
            "title": exam.title,
            "date": exam.exam_date.strftime("%m-%d"),
            "score": score.score,
            "full_score": exam.full_score,
        }
        for score, exam in reversed(rows)
    ]


def exam_stats(exam, class_size=None):
    if class_size is None:
        class_size = Student.query.filter_by(
            teacher_id=current_user.id,
            class_group_id=exam.class_group_id,
            archived=False,
        ).count()
    scores = score_query_for_exam(exam).all()
    entered_count = sum(1 for item in scores if item.status != "pending")
    numeric_scores = [
        item.score
        for item in scores
        if item.status == "scored" and item.score is not None
    ]
    average = None
    pass_rate = None
    excellent_rate = None
    if numeric_scores:
        average = round(sum(numeric_scores) / len(numeric_scores), 1)
        rule = default_grade_rule()
        pass_count = sum(
            1
            for value in numeric_scores
            if score_percent(value, exam.full_score) >= rule.pass_min
        )
        excellent_count = sum(
            1
            for value in numeric_scores
            if score_percent(value, exam.full_score) >= rule.excellent_min
        )
        pass_rate = round(pass_count / len(numeric_scores) * 100, 1)
        excellent_rate = round(excellent_count / len(numeric_scores) * 100, 1)
    pending_count = max(class_size - entered_count, 0)
    progress = round(entered_count / class_size * 100) if class_size else 0
    return SimpleNamespace(
        average=average,
        pass_rate=pass_rate,
        excellent_rate=excellent_rate,
        entered_count=entered_count,
        pending_count=pending_count,
        class_size=class_size,
        progress=progress,
        numeric_count=len(numeric_scores),
    )


def exam_average(exam):
    return exam_stats(exam).average


def exam_distribution(exam):
    bins = [
        {"label": "60 以下", "min": 0, "max": 59, "count": 0},
        {"label": "60-69", "min": 60, "max": 69, "count": 0},
        {"label": "70-79", "min": 70, "max": 79, "count": 0},
        {"label": "80-89", "min": 80, "max": 89, "count": 0},
        {"label": "90-100", "min": 90, "max": 100, "count": 0},
    ]
    scores = score_query_for_exam(exam).filter_by(status="scored").all()
    for item in scores:
        percent = score_percent(item.score, exam.full_score)
        if percent is None:
            continue
        for bucket in bins:
            if bucket["min"] <= percent <= bucket["max"]:
                bucket["count"] += 1
                break
    return bins


def focus_students(exam, limit=None):
    students = students_for_class(exam.class_group)
    score_map = {item.student_id: item for item in score_query_for_exam(exam).all()}
    rule = default_grade_rule()
    rows = []
    for student in students:
        score = score_map.get(student.id)
        if score is None or score.status == "pending":
            rows.append({"student": student, "reason": "成绩待录入", "tone": "warning"})
            continue
        if score.status != "scored":
            rows.append(
                {
                    "student": student,
                    "reason": f"{score_status_label(score)}，需要后续处理",
                    "tone": "info",
                }
            )
            continue
        percent = score_percent(score.score, exam.full_score)
        change = score_change(score, exam)
        if percent is not None and percent < rule.pass_min:
            rows.append(
                {
                    "student": student,
                    "reason": f"本次 {score.score} 分，低于及格线",
                    "tone": "danger",
                }
            )
        elif change is not None and change <= -10:
            rows.append(
                {
                    "student": student,
                    "reason": f"较上次下降 {abs(change):g} 分",
                    "tone": "danger",
                }
            )
    return rows[:limit] if limit else rows


def student_average(student, term_id=None, subject_id=None):
    query = (
        db.session.query(Score.score)
        .join(Exam, Score.exam_id == Exam.id)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student.id,
            Score.status == "scored",
            Score.score.isnot(None),
        )
    )
    if term_id is not None:
        query = query.filter(Exam.term_id == term_id)
    if subject_id is not None:
        query = query.filter(Exam.subject_id == subject_id)
    values = [row.score for row in query.all()]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def student_rank(student, classmates, term_id=None):
    averages = []
    for classmate in classmates:
        average = student_average(classmate, term_id=term_id)
        if average is not None:
            averages.append((classmate.id, average))
    averages.sort(key=lambda item: item[1], reverse=True)
    for index, (student_id, _) in enumerate(averages, start=1):
        if student_id == student.id:
            return index, len(averages)
    return None, len(averages)


def latest_student_score(student, term_id=None, subject_id=None):
    query = (
        db.session.query(Score, Exam)
        .join(Exam, Score.exam_id == Exam.id)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student.id,
            Score.status == "scored",
            Score.score.isnot(None),
        )
    )
    if term_id is not None:
        query = query.filter(Exam.term_id == term_id)
    if subject_id is not None:
        query = query.filter(Exam.subject_id == subject_id)
    return query.order_by(Exam.exam_date.desc(), Exam.id.desc()).first()


def subject_averages_for_student(student, term_id=None):
    query = (
        db.session.query(
            Subject.name,
            Subject.color,
            func.avg(Score.score).label("average"),
        )
        .select_from(Score)
        .join(Exam, Score.exam_id == Exam.id)
        .join(Subject, Exam.subject_id == Subject.id)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student.id,
            Score.status == "scored",
            Score.score.isnot(None),
        )
    )
    if term_id is not None:
        query = query.filter(Exam.term_id == term_id)
    rows = query.group_by(Subject.id).order_by(Subject.name.asc()).all()
    return [
        {
            "name": row.name,
            "color": row.color,
            "average": round(row.average, 1),
        }
        for row in rows
    ]


def trend_data_for_exams(exams):
    labels = []
    values = []
    for exam in exams:
        stats = exam_stats(exam)
        labels.append(exam.exam_date.strftime("%m-%d"))
        values.append(stats.average)
    return {"labels": labels, "values": values}


def median_value(values):
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return round((ordered[midpoint - 1] + ordered[midpoint]) / 2, 1)


def standard_deviation(values):
    if len(values) < 2:
        return None
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    return round(math.sqrt(variance), 1)


def exam_analysis_rows(exam):
    students = students_for_class(exam.class_group)
    score_map = {item.student_id: item for item in score_query_for_exam(exam).all()}
    rows = []
    for student in students:
        score = score_map.get(student.id)
        change = score_change(score, exam)
        rows.append(
            {
                "student": student,
                "score": score,
                "value": score.score if score and score.status == "scored" else None,
                "status_label": score_status_label(score),
                "grade": grade_for_score(score.score, exam.full_score)
                if score and score.status == "scored"
                else "—",
                "change": change,
            }
        )
    return rows


def latest_exam_summary(exam, stats):
    if exam is None or stats is None:
        return SimpleNamespace(
            median=None,
            highest=None,
            lowest=None,
            gap=None,
            standard_deviation=None,
            low_count=0,
            decline_count=0,
            improved_count=0,
            non_numeric_count=0,
            completion_rate=0,
            score_rows=[],
            top_improvers=[],
            top_decliners=[],
        )

    rows = exam_analysis_rows(exam)
    numeric_rows = [row for row in rows if row["value"] is not None]
    values = [row["value"] for row in numeric_rows]
    rule = default_grade_rule()
    lowest = min(numeric_rows, key=lambda row: row["value"]) if numeric_rows else None
    highest = max(numeric_rows, key=lambda row: row["value"]) if numeric_rows else None
    low_count = sum(
        1
        for row in numeric_rows
        if score_percent(row["value"], exam.full_score) < rule.pass_min
    )
    top_improvers = sorted(
        [row for row in numeric_rows if row["change"] is not None and row["change"] > 0],
        key=lambda row: row["change"],
        reverse=True,
    )[:5]
    top_decliners = sorted(
        [row for row in numeric_rows if row["change"] is not None and row["change"] < 0],
        key=lambda row: row["change"],
    )[:5]
    non_numeric_count = sum(
        1
        for row in rows
        if row["score"] is not None and row["score"].status not in ["pending", "scored"]
    )
    return SimpleNamespace(
        median=median_value(values),
        highest=highest,
        lowest=lowest,
        gap=(highest["value"] - lowest["value"]) if highest and lowest else None,
        standard_deviation=standard_deviation(values),
        low_count=low_count,
        decline_count=sum(1 for row in numeric_rows if row["change"] is not None and row["change"] <= -10),
        improved_count=sum(1 for row in numeric_rows if row["change"] is not None and row["change"] > 0),
        non_numeric_count=non_numeric_count,
        completion_rate=stats.progress,
        score_rows=rows,
        top_improvers=top_improvers,
        top_decliners=top_decliners,
    )


def exam_compare_rows(exams):
    rows = []
    previous_average = None
    for exam in exams:
        stats = exam_stats(exam)
        change = None
        if previous_average is not None and stats.average is not None:
            change = round(stats.average - previous_average, 1)
        rows.append({"exam": exam, "stats": stats, "change": change})
        previous_average = stats.average
    return list(reversed(rows[-6:]))


def distribution_rows(exam, numeric_count):
    rows = exam_distribution(exam) if exam else []
    for row in rows:
        row["share"] = round(row["count"] / numeric_count * 100, 1) if numeric_count else 0
    return rows


def current_greeting():
    hour = datetime.now().hour
    if hour < 11:
        return "上午好"
    if hour < 14:
        return "中午好"
    if hour < 18:
        return "下午好"
    return "晚上好"


@app.route("/")
@login_required
def dashboard():
    workspace = get_workspace()
    if workspace.class_group is None:
        return render_template("index.html", empty=True)

    exams_query = Exam.query.filter_by(
        teacher_id=current_user.id,
        class_group_id=workspace.class_group.id,
    )
    if workspace.term is not None:
        exams_query = exams_query.filter_by(term_id=workspace.term.id)
    if workspace.subject is not None:
        exams_query = exams_query.filter_by(subject_id=workspace.subject.id)
    exams = exams_query.order_by(Exam.exam_date.desc(), Exam.id.desc()).all()
    latest_exam = exams[0] if exams else None
    previous_exam = exams[1] if len(exams) > 1 else None

    latest_stats = exam_stats(latest_exam) if latest_exam else None
    previous_average = exam_stats(previous_exam).average if previous_exam else None
    average_change = None
    if latest_stats and latest_stats.average is not None and previous_average is not None:
        average_change = round(latest_stats.average - previous_average, 1)

    focus_rows = focus_students(latest_exam, limit=5) if latest_exam else []
    trend_exams = list(reversed(exams[:6]))
    tasks = []
    if latest_exam and latest_stats.pending_count:
        tasks.append(
            {
                "title": "需要补录成绩",
                "body": f"{latest_exam.title} 还有 {latest_stats.pending_count} 名学生未录入",
                "url": url_for("exam_entry", exam_id=latest_exam.id),
            }
        )
    if focus_rows:
        tasks.append(
            {
                "title": "成绩异常",
                "body": f"{focus_rows[0]['student'].name}{focus_rows[0]['reason']}",
                "url": url_for("analysis_class"),
            }
        )
    if not tasks:
        tasks.append(
            {
                "title": "暂无紧急事项",
                "body": "最近一次考试没有明显待处理问题。",
                "url": url_for("exams"),
            }
        )

    return render_template(
        "index.html",
        empty=False,
        greeting=current_greeting(),
        exams_count=len(exams),
        latest_exam=latest_exam,
        latest_stats=latest_stats,
        average_change=average_change,
        focus_rows=focus_rows,
        tasks=tasks,
        trend_data=trend_data_for_exams(trend_exams),
    )


@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    workspace = get_workspace()
    if workspace.class_group is None:
        flash("请先创建班级。", "warning")
        return redirect(url_for("settings"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        student_number = (request.form.get("student_number") or "").strip() or None
        if not name or len(name) > 40:
            flash("学生姓名无效。", "warning")
            return redirect(url_for("students"))
        duplicate = Student.query.filter_by(
            teacher_id=current_user.id,
            class_group_id=workspace.class_group.id,
            name=name,
        ).first()
        if duplicate:
            flash("该班级已存在同名学生。", "warning")
            return redirect(url_for("students"))
        db.session.add(
            Student(
                teacher_id=current_user.id,
                class_group_id=workspace.class_group.id,
                name=name,
                student_number=student_number,
            )
        )
        db.session.commit()
        flash("学生已加入班级。", "success")
        return redirect(url_for("students"))

    rows = []
    for student in students_for_class(workspace.class_group):
        latest = latest_student_score(
            student,
            term_id=workspace.term.id if workspace.term else None,
            subject_id=workspace.subject.id if workspace.subject else None,
        )
        rows.append(
            {
                "student": student,
                "average": student_average(
                    student,
                    term_id=workspace.term.id if workspace.term else None,
                    subject_id=workspace.subject.id if workspace.subject else None,
                ),
                "latest": latest,
            }
        )
    return render_template("students.html", rows=rows)


@app.route("/students/<int:student_id>", methods=["GET", "POST"])
@login_required
def student_detail(student_id):
    student = object_for_teacher_or_404(Student, student_id)
    workspace = get_workspace()
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        note_date = parse_date(request.form.get("note_date"), date.today())
        if not content:
            flash("教师记录不能为空。", "warning")
        else:
            db.session.add(
                TeacherNote(
                    teacher_id=current_user.id,
                    student_id=student.id,
                    note_date=note_date,
                    content=content,
                )
            )
            db.session.commit()
            flash("教师记录已保存。", "success")
        return redirect(url_for("student_detail", student_id=student.id))

    classmates = students_for_class(student.class_group)
    rank, ranked_count = student_rank(
        student,
        classmates,
        term_id=workspace.term.id if workspace.term else None,
    )
    score_rows = (
        db.session.query(Score, Exam, Subject)
        .join(Exam, Score.exam_id == Exam.id)
        .join(Subject, Exam.subject_id == Subject.id)
        .filter(
            Score.teacher_id == current_user.id,
            Score.student_id == student.id,
            Score.status == "scored",
            Score.score.isnot(None),
        )
        .order_by(Exam.exam_date.asc(), Exam.id.asc())
        .all()
    )
    trend_data = {
        "labels": [exam.exam_date.strftime("%m-%d") for _, exam, _ in score_rows],
        "values": [score.score for score, _, _ in score_rows],
    }
    timeline = list(reversed(score_rows[-6:]))
    return render_template(
        "student_detail.html",
        student=student,
        average=student_average(
            student,
            term_id=workspace.term.id if workspace.term else None,
        ),
        rank=rank,
        ranked_count=ranked_count,
        subject_rows=subject_averages_for_student(
            student,
            term_id=workspace.term.id if workspace.term else None,
        ),
        trend_data=trend_data,
        timeline=timeline,
    )


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = object_for_teacher_or_404(Student, student_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        student_number = (request.form.get("student_number") or "").strip() or None
        duplicate = Student.query.filter(
            Student.teacher_id == current_user.id,
            Student.class_group_id == student.class_group_id,
            Student.name == name,
            Student.id != student.id,
        ).first()
        if not name or len(name) > 40:
            flash("学生姓名无效。", "warning")
        elif duplicate:
            flash("该班级已存在同名学生。", "warning")
        else:
            student.name = name
            student.student_number = student_number
            db.session.commit()
            flash("学生信息已更新。", "success")
            return redirect(url_for("student_detail", student_id=student.id))
    return render_template("edit.html", student=student)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):
    student = object_for_teacher_or_404(Student, student_id)
    db.session.delete(student)
    db.session.commit()
    flash("学生已删除。", "info")
    return redirect(url_for("students"))


@app.route("/student/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit(student_id):
    return redirect(url_for("edit_student", student_id=student_id))


@app.route("/student/delete/<int:student_id>", methods=["POST"])
@login_required
def delete(student_id):
    return delete_student(student_id)


@app.route("/student/course/<int:student_id>")
@login_required
def course(student_id):
    return redirect(url_for("student_detail", student_id=student_id))


@app.route("/exams", methods=["GET", "POST"])
@login_required
def exams():
    workspace = get_workspace()
    if workspace.class_group is None or workspace.term is None:
        flash("请先创建班级和学期。", "warning")
        return redirect(url_for("settings"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        exam_type = (request.form.get("exam_type") or "单元测试").strip()
        exam_date = parse_date(request.form.get("exam_date"))
        subject_id = request.form.get("subject_id", type=int)
        full_score_raw = request.form.get("full_score") or "100"
        subject = Subject.query.filter_by(
            id=subject_id,
            teacher_id=current_user.id,
        ).first()
        try:
            full_score = int(full_score_raw)
        except ValueError:
            full_score = 0
        duplicate = None
        if subject is not None:
            duplicate = Exam.query.filter_by(
                teacher_id=current_user.id,
                class_group_id=workspace.class_group.id,
                term_id=workspace.term.id,
                subject_id=subject.id,
                title=title,
            ).first()
        if not title or len(title) > 80:
            flash("考试名称无效。", "warning")
        elif subject is None:
            flash("请选择有效科目。", "warning")
        elif exam_date is None:
            flash("考试日期无效。", "warning")
        elif full_score < 1 or full_score > 300:
            flash("满分必须在 1-300 之间。", "warning")
        elif duplicate:
            flash("该考试已经存在。", "warning")
        else:
            exam = Exam(
                teacher_id=current_user.id,
                class_group_id=workspace.class_group.id,
                term_id=workspace.term.id,
                subject_id=subject.id,
                title=title,
                exam_type=exam_type or "单元测试",
                exam_date=exam_date,
                full_score=full_score,
            )
            db.session.add(exam)
            db.session.commit()
            session["subject_id"] = subject.id
            flash("考试已创建，可以开始录入成绩。", "success")
            return redirect(url_for("exam_entry", exam_id=exam.id))
        return redirect(url_for("exams"))

    query = Exam.query.filter_by(
        teacher_id=current_user.id,
        class_group_id=workspace.class_group.id,
        term_id=workspace.term.id,
    )
    if workspace.subject is not None:
        query = query.filter_by(subject_id=workspace.subject.id)
    exam_rows = []
    for exam in query.order_by(Exam.exam_date.desc(), Exam.id.desc()).all():
        exam_rows.append({"exam": exam, "stats": exam_stats(exam)})
    return render_template("exams.html", exam_rows=exam_rows)


@app.route("/exams/<int:exam_id>/delete", methods=["POST"])
@login_required
def delete_exam(exam_id):
    exam = object_for_teacher_or_404(Exam, exam_id)
    db.session.delete(exam)
    db.session.commit()
    flash(f"“{exam.title}”已删除。", "info")
    return redirect(url_for("exams"))


@app.route("/exams/<int:exam_id>/entry")
@login_required
def exam_entry(exam_id):
    exam = object_for_teacher_or_404(Exam, exam_id)
    students = students_for_class(exam.class_group)
    score_map = {item.student_id: item for item in score_query_for_exam(exam).all()}
    rows = []
    for student in students:
        score = score_map.get(student.id)
        history = recent_scores(
            student.id,
            class_group_id=exam.class_group_id,
            term_id=exam.term_id,
            subject_id=exam.subject_id,
        )
        rows.append(
            {
                "student": student,
                "score": score,
                "display": score_display(score),
                "status_label": score_status_label(score),
                "grade": grade_for_score(score.score, exam.full_score)
                if score and score.status == "scored"
                else "—",
                "change": score_change(score, exam),
                "history": history,
            }
        )
    return render_template(
        "exam_entry.html",
        exam=exam,
        rows=rows,
        stats=exam_stats(exam, class_size=len(students)),
    )


@app.route("/exams/<int:exam_id>/export.csv")
@login_required
def export_exam_scores(exam_id):
    exam = object_for_teacher_or_404(Exam, exam_id)
    students = students_for_class(exam.class_group)
    score_map = {item.student_id: item for item in score_query_for_exam(exam).all()}
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["学号", "姓名", "成绩", "状态", "等级", "备注"])
    for student in students:
        score = score_map.get(student.id)
        writer.writerow(
            [
                student.student_number or "",
                student.name,
                score_display(score),
                score_status_label(score),
                grade_for_score(score.score, exam.full_score)
                if score and score.status == "scored"
                else "",
                score.remark if score and score.remark else "",
            ]
        )
    filename = f"exam-{exam.id}-scores.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/exams/<int:exam_id>/import", methods=["POST"])
@login_required
def import_exam_scores(exam_id):
    exam = object_for_teacher_or_404(Exam, exam_id)
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        flash("请选择 CSV 文件。", "warning")
        return redirect(url_for("exam_entry", exam_id=exam.id))

    content = uploaded.stream.read().decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    students = students_for_class(exam.class_group)
    by_number = {
        student.student_number: student
        for student in students
        if student.student_number
    }
    by_name = {student.name: student for student in students}
    updated_count = 0
    skipped_count = 0
    for row in reader:
        student_number = (row.get("学号") or row.get("student_number") or "").strip()
        student_name = (row.get("姓名") or row.get("name") or "").strip()
        score_raw = (row.get("成绩") or row.get("score") or "").strip()
        status_raw = (row.get("状态") or row.get("status") or "").strip()
        remark = (row.get("备注") or row.get("remark") or "").strip() or None
        student = by_number.get(student_number) or by_name.get(student_name)
        if student is None:
            skipped_count += 1
            continue
        try:
            status, score_value = normalize_score_input(score_raw or status_raw, exam.full_score)
        except ValueError:
            skipped_count += 1
            continue
        score = Score.query.filter_by(
            teacher_id=current_user.id,
            exam_id=exam.id,
            student_id=student.id,
        ).first()
        if score is None:
            score = Score(
                teacher_id=current_user.id,
                exam_id=exam.id,
                student_id=student.id,
            )
            db.session.add(score)
        score.status = status
        score.score = score_value
        score.remark = remark
        updated_count += 1
    db.session.commit()
    flash(f"已导入 {updated_count} 条成绩，跳过 {skipped_count} 条。", "success")
    return redirect(url_for("exam_entry", exam_id=exam.id))


@app.route("/api/exams/<int:exam_id>/scores/<int:student_id>", methods=["POST"])
@login_required
def save_score(exam_id, student_id):
    exam = object_for_teacher_or_404(Exam, exam_id)
    student = object_for_teacher_or_404(Student, student_id)
    if student.class_group_id != exam.class_group_id:
        return jsonify({"ok": False, "error": "学生不属于该考试班级。"}), 403

    payload = request.get_json(silent=True) or request.form
    raw_score = payload.get("score", "")
    remark = (payload.get("remark") or "").strip() or None
    try:
        status, score_value = normalize_score_input(raw_score, exam.full_score)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    score = Score.query.filter_by(
        teacher_id=current_user.id,
        exam_id=exam.id,
        student_id=student.id,
    ).first()
    if score is None:
        score = Score(
            teacher_id=current_user.id,
            exam_id=exam.id,
            student_id=student.id,
        )
        db.session.add(score)
    score.status = status
    score.score = score_value
    score.remark = remark
    db.session.commit()

    stats = exam_stats(exam)
    change = score_change(score, exam)
    return jsonify(
        {
            "ok": True,
            "display": score_display(score),
            "status": score.status,
            "status_label": score_status_label(score),
            "grade": grade_for_score(score.score, exam.full_score)
            if score.status == "scored"
            else "—",
            "change": change,
            "change_label": format_change(change),
            "updated_at": score.updated_at.strftime("%H:%M"),
            "progress": {
                "entered": stats.entered_count,
                "total": stats.class_size,
                "percent": stats.progress,
            },
        }
    )


@app.route("/analysis/class")
@login_required
def analysis_class():
    workspace = get_workspace()
    if workspace.class_group is None or workspace.term is None:
        flash("请先创建班级和学期。", "warning")
        return redirect(url_for("settings"))

    query = Exam.query.filter_by(
        teacher_id=current_user.id,
        class_group_id=workspace.class_group.id,
        term_id=workspace.term.id,
    )
    if workspace.subject is not None:
        query = query.filter_by(subject_id=workspace.subject.id)
    exams = query.order_by(Exam.exam_date.asc(), Exam.id.asc()).all()
    latest_exam = exams[-1] if exams else None
    latest_stats = exam_stats(latest_exam) if latest_exam else None
    previous_stats = exam_stats(exams[-2]) if len(exams) > 1 else None
    change = None
    if latest_stats and previous_stats and latest_stats.average is not None:
        if previous_stats.average is not None:
            change = round(latest_stats.average - previous_stats.average, 1)
    focus_rows = focus_students(latest_exam, limit=8) if latest_exam else []
    summary = latest_exam_summary(latest_exam, latest_stats)
    distribution = distribution_rows(
        latest_exam,
        latest_stats.numeric_count if latest_stats else 0,
    )
    conclusion = "暂无足够考试数据，请先创建考试并录入成绩。"
    if latest_exam and latest_stats:
        direction = "保持稳定"
        if change is not None and change > 0:
            direction = f"较上次提高 {change:g} 分"
        elif change is not None and change < 0:
            direction = f"较上次下降 {abs(change):g} 分"
        conclusion = (
            f"{latest_exam.title} 平均分 {format_number(latest_stats.average)}，"
            f"{direction}。需要关注 {len(focus_rows)} 名学生。"
        )
    return render_template(
        "analysis_class.html",
        exams=exams,
        latest_exam=latest_exam,
        latest_stats=latest_stats,
        previous_stats=previous_stats,
        average_change=change,
        summary=summary,
        focus_rows=focus_rows,
        conclusion=conclusion,
        trend_data=trend_data_for_exams(exams),
        distribution=distribution,
        compare_rows=exam_compare_rows(exams),
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = (request.form.get("name") or "").strip()
            username = (request.form.get("username") or "").strip()
            duplicate = Teacher.query.filter(
                Teacher.username == username,
                Teacher.id != current_user.id,
            ).first()
            if not name or not username:
                flash("姓名和用户名不能为空。", "warning")
            elif duplicate:
                flash("用户名已被占用。", "warning")
            else:
                current_user.name = name
                current_user.username = username
                db.session.commit()
                flash("账号信息已保存。", "success")
        elif action == "class":
            name = (request.form.get("name") or "").strip()
            school_year = (request.form.get("school_year") or "2026").strip()
            if not name:
                flash("班级名称不能为空。", "warning")
            elif ClassGroup.query.filter_by(
                teacher_id=current_user.id,
                name=name,
            ).first():
                flash("班级已存在。", "warning")
            else:
                class_group = ClassGroup(
                    teacher_id=current_user.id,
                    name=name,
                    school_year=school_year,
                )
                db.session.add(class_group)
                db.session.commit()
                session["class_group_id"] = class_group.id
                flash("班级已创建。", "success")
        elif action == "term":
            class_group_id = request.form.get("class_group_id", type=int)
            class_group = ClassGroup.query.filter_by(
                id=class_group_id,
                teacher_id=current_user.id,
            ).first()
            name = (request.form.get("name") or "").strip()
            starts_on = parse_date(request.form.get("starts_on"), date.today())
            ends_on = parse_date(request.form.get("ends_on"))
            is_active = bool(request.form.get("is_active"))
            if class_group is None or not name:
                flash("请选择班级并填写学期名称。", "warning")
            else:
                if is_active:
                    Term.query.filter_by(
                        teacher_id=current_user.id,
                        class_group_id=class_group.id,
                    ).update({"is_active": False})
                term = Term(
                    teacher_id=current_user.id,
                    class_group_id=class_group.id,
                    name=name,
                    starts_on=starts_on,
                    ends_on=ends_on,
                    is_active=is_active,
                )
                db.session.add(term)
                db.session.commit()
                session["term_id"] = term.id
                flash("学期已创建。", "success")
        elif action == "subject":
            name = (request.form.get("name") or "").strip()
            color = (request.form.get("color") or "#C96442").strip()
            if not name:
                flash("科目名称不能为空。", "warning")
            elif Subject.query.filter_by(teacher_id=current_user.id, name=name).first():
                flash("科目已存在。", "warning")
            else:
                subject = Subject(teacher_id=current_user.id, name=name, color=color)
                db.session.add(subject)
                db.session.commit()
                session["subject_id"] = subject.id
                flash("科目已创建。", "success")
        elif action == "grade_rule":
            excellent_min = request.form.get("excellent_min", type=int)
            pass_min = request.form.get("pass_min", type=int)
            if (
                excellent_min is None
                or pass_min is None
                or pass_min < 0
                or excellent_min > 100
                or pass_min >= excellent_min
            ):
                flash("等级规则无效，及格线必须低于优秀线。", "warning")
            else:
                rule = GradeRule.query.filter_by(teacher_id=current_user.id).first()
                if rule is None:
                    rule = GradeRule(teacher_id=current_user.id)
                    db.session.add(rule)
                rule.pass_min = pass_min
                rule.excellent_min = excellent_min
                db.session.commit()
                flash("等级规则已保存。", "success")
        return redirect(url_for("settings"))

    workspace = get_workspace()
    return render_template(
        "settings.html",
        class_groups=workspace.class_groups,
        subjects=workspace.subjects,
        grade_rule=default_grade_rule(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        teacher = Teacher.query.filter_by(username=username).first()
        if teacher and teacher.validate_password(password):
            login_user(teacher)
            flash("欢迎回来。", "success")
            return redirect(url_for("dashboard"))
        flash("用户名或密码错误。", "warning")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("已退出登录。", "info")
    return redirect(url_for("login"))


@app.route("/api/login_status")
def login_status():
    return jsonify({"status": "success" if current_user.is_authenticated else "anonymous"})
