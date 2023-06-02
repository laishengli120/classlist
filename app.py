import os
from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask import request, redirect, url_for, flash
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flask_login import current_user
from sqlalchemy.orm import validates
from datetime import date

app = Flask(__name__)
# app.config['SECRET_KEY'] = 'dev'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + os.path.join(os.path.dirname(app.root_path), os.getenv('DATABASE_FILE', 'data.db'))
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config
db = SQLAlchemy(app)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    username = db.Column(db.String(20))
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def validate_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    courses = db.relationship('StudentCourse', backref='student', cascade='all, delete-orphan')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    students = db.relationship('StudentCourse', backref='course', cascade='all, delete-orphan')

class StudentCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    score = db.Column(db.Integer)
    exam_date = db.Column(db.Date)

    @validates('score')
    def validate_score(self, key, score):
        assert score >= 0 and score <= 100, '分数必须在0-100之间'
        return score
    # @validates('exam_date')
    # def validate_exam_date(self, key, exam_date):
    #     assert exam_date <= datetime.date.today(), '考试日期必须小于今天'
    #     return exam_date
                          

import click

@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')
@app.cli.command()
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    db.create_all()
    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password)
    else:
        click.echo('Creating user...')
        user = User(username=username, name='Admin')
        user.set_password(password)
        db.session.add(user)
    db.session.commit()
    click.echo('Done.')

@app.context_processor
def inject_user():
    user = User.query.first()
    return dict(user=user)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('index'))
        name = request.form.get('name')
        if not name or len(name) > 20:
            flash('无效输入！')
            return redirect(url_for('index'))
        elif Student.query.filter_by(name=name).first():
            flash('名字已经存在！', 'warning')
            return redirect(url_for('index'))
        student = Student(name=name)
        db.session.add(student)
        db.session.commit()
        flash('添加成功！', 'success')
        return redirect(url_for('index'))
    students = Student.query.all()
    return render_template('index.html', students=students)
@app.route('/student/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == 'POST':
        name = request.form.get('name')
        if not name or len(name) > 20:
            flash('无效输入！', 'warning')
            return redirect(url_for('edit', student_id=student_id))
        elif Student.query.filter_by(name=name).first():
            flash('名字已经存在！', 'warning')
            return redirect(url_for('edit', student_id=student_id))
        student.name = name
        db.session.commit()
        flash('更新成功！')
        return redirect(url_for('index'))
    return render_template('edit.html', student=student)
@app.route('/student/course/<int:student_id>', methods=['POST', 'GET'])
def course(student_id):
    student = Student.query.get_or_404(student_id)
    course = request.form.get('course', None)  # 获取课程名，如果不存在则为None
    score = request.form.get('score', None)  # 获取成绩，如果不存在则为None
    exam_date = request.form.get('exam_date', None)  # 获取考试日期，如果不存在则为None

    # 如果课程名、成绩和考试日期都存在，则创建一个新的StudentCourse对象
    if course and score and exam_date:
        course_obj = Course.query.filter_by(name=course).first()
        if not course_obj:
            course_obj = Course(name=course)
            db.session.add(course_obj)
            db.session.commit()
        
        student_course = StudentCourse(
            student_id=student.id, 
            course_id=course_obj.id, 
            score=int(score), 
            exam_date=date.fromisoformat(exam_date)
        )
        db.session.add(student_course)
        db.session.commit()
        flash('添加成绩成功！')
    return render_template('course.html', student=student)
@app.route('/student/delete/<int:student_id>', methods=['POST'])
@login_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('删除成功！', 'success')
    return redirect(url_for('index'))
@app.route('/student/delete_course/<int:student_id>/<int:course_id>', methods=['POST'])
@login_required
def delete_course(student_id, course_id):
    student_course = StudentCourse.query.filter_by(student_id=student_id, course_id=course_id).first()
    db.session.delete(student_course)
    db.session.commit()
    flash('删除成功！', 'success')
    return redirect(url_for('course', student_id=student_id))
login_manager = LoginManager(app)
login_manager.login_view = 'login'
@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    return user
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password= request.form['password']
        if not username or not password:
            flash('无效输入！', 'warning')
            return redirect(url_for('login'))
        user = User.query.first()
        if username == user.username and user.validate_password(password):
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        flash('用户名或密码错误！', 'warning')
        return redirect(url_for('login'))
    return render_template('login.html')
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('再会！', 'info')
    return redirect(url_for('index'))
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']
        if not name or len(name) > 20:
            flash('无效输入！', 'warning')
            return redirect(url_for('setting'))
        current_user.name = name
        db.session.commit()
        flash('更新成功！', 'success')
        return redirect(url_for('index'))
    return render_template('settings.html')

@app.route('/api/student/course/<int:student_id>', methods=['GET'])
def get_student_courses(student_id):
    result = db.session.query(
        StudentCourse.course_id
    ).filter(
        StudentCourse.student_id == student_id
    ).group_by(
        StudentCourse.course_id
    ).all()

    return jsonify([row.course_id for row in result])

@app.route('/course/<int:course_id>', methods=['GET'])
def get_course_scores(course_id):
    course_name = db.session.query(
        Course.name
    ).filter(
        Course.id == course_id
    ).first()
    result = db.session.query(
        StudentCourse.exam_date, 
        func.avg(StudentCourse.score).label('average_score')
    ).filter(
        StudentCourse.course_id == course_id
    ).group_by(
        StudentCourse.exam_date
    ).order_by(
        StudentCourse.exam_date
    ).all()

    return jsonify([{
        'course_name': course_name[0],
        'exam_date': row.exam_date.strftime('%Y-%m-%d'), 
        'average_score': float(row.average_score)
    } for row in result])
