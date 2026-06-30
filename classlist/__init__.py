import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


app = Flask(
    __name__,
    instance_relative_config=True,
    template_folder="../templates",
    static_folder="../static",
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.abspath(
    os.getenv("DATABASE_FILE", "data.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    from classlist.models import Teacher

    return Teacher.query.get(int(user_id))


@app.context_processor
def inject_app_name():
    return {"app_name": "成绩簿"}


from classlist import commands, views  # noqa: E402,F401
