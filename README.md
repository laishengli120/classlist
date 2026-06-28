# Classlist

一个 Flask 班级名单与成绩管理应用，支持学生管理、课程成绩录入、管理员登录和 Excel 导入。项目适合用于学习 Flask、SQLAlchemy、Flask-Login 和基础班级数据管理流程。

## 功能

- 学生名单展示和搜索
- 管理员登录后添加、编辑和删除学生
- 为学生录入课程、分数和考试日期
- 分数输入校验
- Excel 导入
- SQLite 本地存储
- Flask CLI 初始化数据库和创建管理员

## 技术栈

- Python / Flask
- Flask-Login
- Flask-SQLAlchemy
- SQLite
- Pandas / openpyxl
- Jinja2
- jQuery

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=classlist
flask initdb
flask admin
flask run
```

打开 `http://127.0.0.1:5000` 访问应用。

## 项目结构

```text
classlist/ 或根目录应用文件  # Flask 应用代码
templates/                  # 页面模板
static/                     # 样式、图片和脚本
requirements.txt            # Python 依赖
data.db                     # SQLite 数据库文件
```

## 维护提醒

- 仓库已提交 `venv/` 和 `data.db`，建议清理历史或后续至少从当前分支删除，并加入 `.gitignore`。
- `.vscode/` 是本地编辑器配置，可按需要保留或忽略。
- 如果数据库含真实学生信息，不应公开。
- 建议明确它与 `laisheng` 仓库的关系，避免两个相似项目长期并行造成维护混乱。
