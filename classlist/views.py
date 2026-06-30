from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from classlist import app, db
from classlist.models import Course, Student, StudentCourse, User


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not current_user.is_authenticated:
            return redirect(url_for("index"))
        name = (request.form.get("name") or "").strip()
        if not name or len(name) > 20:
            flash("无效输入！", "warning")
            return redirect(url_for("index"))
        if Student.query.filter_by(name=name).first():
            flash("名字已经存在！", "warning")
            return redirect(url_for("index"))
        db.session.add(Student(name=name))
        db.session.commit()
        flash("添加成功！", "success")
        return redirect(url_for("index"))

    students = Student.query.order_by(Student.id.asc()).all()
    return render_template("index.html", students=students)


@app.route("/student/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        duplicate = Student.query.filter(Student.name == name, Student.id != student.id).first()
        if not name or len(name) > 20:
            flash("无效输入！", "warning")
            return redirect(url_for("edit", student_id=student_id))
        if duplicate:
            flash("名字已经存在！", "warning")
            return redirect(url_for("edit", student_id=student_id))
        student.name = name
        db.session.commit()
        flash("更新成功！", "success")
        return redirect(url_for("index"))
    return render_template("edit.html", student=student)


@app.route("/student/delete/<int:student_id>", methods=["POST"])
@login_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("删除成功！", "success")
    return redirect(url_for("index"))


@app.route("/student/course/<int:student_id>", methods=["GET", "POST"])
def course(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == "POST":
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        course_name = (request.form.get("course") or "").strip()
        score_raw = request.form.get("score")
        exam_date_raw = request.form.get("exam_date")

        try:
            score = int(score_raw)
        except (TypeError, ValueError):
            flash("无效的分数", "warning")
            return redirect(url_for("course", student_id=student_id))
        if score < 0 or score > 100:
            flash("分数必须在 0-100 之间", "warning")
            return redirect(url_for("course", student_id=student_id))

        try:
            exam_date = date.fromisoformat(exam_date_raw)
        except (TypeError, ValueError):
            flash("考试日期格式错误，正确格式应为 YYYY-MM-DD", "warning")
            return redirect(url_for("course", student_id=student_id))
        if exam_date > date.today():
            flash("考试日期必须在今天之前", "warning")
            return redirect(url_for("course", student_id=student_id))

        if not course_name or len(course_name) > 20:
            flash("课程名称无效", "warning")
            return redirect(url_for("course", student_id=student_id))

        course_obj = Course.query.filter_by(name=course_name).first()
        if course_obj is None:
            course_obj = Course(name=course_name)
            db.session.add(course_obj)
            db.session.flush()

        db.session.add(
            StudentCourse(
                student_id=student.id,
                course_id=course_obj.id,
                score=score,
                exam_date=exam_date,
            )
        )
        db.session.commit()
        flash("添加成绩成功！", "success")
        return redirect(url_for("course", student_id=student_id))

    return render_template("course.html", student=student)


@app.route("/student/<int:student_id>/course/<int:course_id>/delete", methods=["POST"])
@login_required
def delete_course(student_id, course_id):
    score = StudentCourse.query.filter_by(
        student_id=student_id,
        course_id=course_id,
    ).order_by(StudentCourse.exam_date.desc()).first_or_404()
    db.session.delete(score)
    db.session.commit()
    flash("删除成绩成功！", "success")
    return redirect(url_for("course", student_id=student_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.first()
        if user and username == user.username and user.validate_password(password):
            login_user(user)
            flash("登录成功！", "success")
            return redirect(url_for("index"))
        flash("用户名或密码错误！", "warning")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("再会，同志！", "info")
    return redirect(url_for("index"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name or len(name) > 20:
            flash("无效输入！", "warning")
            return redirect(url_for("settings"))
        current_user.name = name
        db.session.commit()
        flash("更新成功！", "success")
        return redirect(url_for("index"))
    return render_template("settings.html")


@app.route("/api/student/course/<int:student_id>")
def get_student_courses(student_id):
    rows = (
        db.session.query(StudentCourse.course_id)
        .filter(StudentCourse.student_id == student_id)
        .group_by(StudentCourse.course_id)
        .all()
    )
    return jsonify([row.course_id for row in rows])


@app.route("/course/<int:course_id>/<int:student_id>")
def get_course_scores(course_id, student_id):
    course_obj = Course.query.get_or_404(course_id)
    rows = (
        db.session.query(
            StudentCourse.exam_date,
            func.avg(StudentCourse.score).label("average_score"),
        )
        .filter(
            StudentCourse.course_id == course_id,
            StudentCourse.student_id == student_id,
        )
        .group_by(StudentCourse.exam_date)
        .order_by(StudentCourse.exam_date.asc())
        .all()
    )
    return jsonify(
        [
            {
                "course_name": course_obj.name,
                "exam_date": row.exam_date.strftime("%Y-%m-%d"),
                "average_score": float(row.average_score),
            }
            for row in rows
        ]
    )


@app.route("/api/login_status")
def login_status():
    return jsonify({"status": "success" if current_user.is_authenticated else "anonymous"})
