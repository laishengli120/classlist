import os
from types import SimpleNamespace

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
    from classlist.models import User

    return User.query.get(int(user_id))


@app.context_processor
def inject_user():
    from classlist.models import User

    user = User.query.first()
    return {"user": user or SimpleNamespace(username="Classlist", name="Classlist")}


from classlist import commands, views  # noqa: E402,F401
