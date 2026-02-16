import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ML_CLIENT_ID = os.getenv("ML_CLIENT_ID")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET")
ML_REDIRECT_URI = os.getenv("ML_REDIRECT_URI")

ML_SITE_ID = os.getenv("ML_SITE_ID", "MLB")
ML_SELLER_USER_ID = os.getenv("ML_SELLER_USER_ID")

ML_TOKENS_FILE = Path(os.getenv("ML_TOKENS_FILE", "ml_tokens.json"))

ML_TIMEOUT = int(os.getenv("ML_TIMEOUT", "30"))
ML_CONCURRENCY = int(os.getenv("ML_CONCURRENCY", "8"))
