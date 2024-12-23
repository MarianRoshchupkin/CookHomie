import click
import sys
import subprocess
from dotenv import load_dotenv

from models import init_db, Base, engine

load_dotenv()

@click.group()
def cli():
    """CLI utility for the MealPlanner bot."""
    pass

@cli.command()
def initdb():
    """
    Initializes the database, creating all tables if they don't exist.
    """
    click.echo("Initializing the database...")
    try:
        init_db()
        click.echo("Tables created successfully!")
    except Exception as e:
        click.echo(f"Error creating tables: {e}")

@cli.command()
def runbot():
    """
    Runs the Telegram bot.
    """
    click.echo("Starting Telegram bot...")
    try:
        subprocess.run([sys.executable, "bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Error running bot: {e}")

@cli.command()
def resetdb():
    """
    Drops all tables and re-creates them.
    """
    confirm = click.prompt(
        "Are you sure you want to reset the database? This is irreversible. Type 'yes' to continue",
        default="no"
    )
    if confirm.lower() == "yes":
        click.echo("Resetting database...")
        try:
            Base.metadata.drop_all(engine)
            click.echo("All tables dropped.")
            init_db()
            click.echo("Database re-initialized.")
        except Exception as e:
            click.echo(f"Error resetting the database: {e}")
    else:
        click.echo("Database reset canceled.")

if __name__ == "__main__":
    cli()