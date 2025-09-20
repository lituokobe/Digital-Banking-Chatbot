import os
from pathlib import Path
from dotenv import load_dotenv

# get the absolute directory of the project
basic_dir = Path(__file__).resolve().parent.parent

# get the environment file and load it
env_path = os.path.join(basic_dir, '.env')
load_dotenv(dotenv_path=env_path)

# API and urls
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# database
banking_data_excel = f"{basic_dir}/database/banking_data.xlsx"
banking_data_db = f"{basic_dir}/database/banking_data.db"
digital_banking_FAQ = f'{basic_dir}/database/digital_banking_FAQ.md'