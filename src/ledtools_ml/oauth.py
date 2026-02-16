import requests
from .config import ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI
from .tokens import save_tokens

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

def exchange_code_for_token(code: str, tokens_file):
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": ML_REDIRECT_URI,
        },
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ml-oauth-token-script/1.0",
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    save_tokens(tokens_file, data)
    return data

def refresh_access_token(refresh_token: str, tokens_file):
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": ML_CLIENT_ID,
            "client_secret": ML_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    save_tokens(tokens_file, data)
    return data
