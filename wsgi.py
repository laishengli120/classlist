import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if load_dotenv and os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from classlist import app
