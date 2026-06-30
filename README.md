# Classlist

一个 Flask / Jinja 成绩管理应用，已经重构为 **Warm Minimal Academic Workspace** 风格的教师成绩工作台：暖白背景、低饱和配色、左侧导航、学生档案、考试记录、批量成绩录入和班级分析。

## 功能

- 多教师登录，教师之间的数据相互隔离
- 班级、学期、科目和评分规则管理
- 学生名单、学生档案和教师观察记录
- 考试记录创建与删除
- 按“考试 × 全班学生”批量录入成绩
- 成绩自动保存，支持数字分数和 `缺`、`病`、`免` 状态
- 班级平均分、及格率、优秀率、趋势、分布和关注学生分析
- 默认演示数据：李老师、四年级 2 班、2026 年春季学期、数学考试记录

## 技术栈

- Python / Flask
- Flask-Login
- Flask-SQLAlchemy
- SQLite
- Jinja2
- Chart.js
- 原生 JavaScript

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=classlist
flask initdb --drop
flask run
```

打开 `http://127.0.0.1:5000` 访问应用。

默认演示账号：

```text
用户名：admin
密码：admin
```

## CLI

```bash
flask initdb --drop
```

删除当前 SQLite 数据库里的所有表，重新创建新模型，并写入默认演示数据。这个项目不兼容旧版 `Course` / `StudentCourse` 数据结构。

```bash
flask admin
```

创建或更新教师账号。

## 项目结构

```text
classlist/      Flask 应用、模型、路由和 CLI
templates/      Jinja 页面模板
static/         CSS、图表脚本、成绩录入脚本和图片资源
requirements.txt
wsgi.py
```
