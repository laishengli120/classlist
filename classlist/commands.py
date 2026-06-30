import click

from classlist import app, db
from classlist.models import User


@app.cli.command()
@click.option("--drop", is_flag=True, help="Drop existing tables before creating them.")
def initdb(drop):
    if drop:
        db.drop_all()
    db.create_all()
    click.echo("Initialized database.")


@app.cli.command()
@click.option("--username", prompt=True, help="The username used to log in.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="The password used to log in.",
)
def admin(username, password):
    db.create_all()
    user = User.query.first()
    if user is None:
        user = User(username=username, name="Admin")
        db.session.add(user)
    else:
        user.username = username
    user.set_password(password)
    db.session.commit()
    click.echo("Admin user saved.")
