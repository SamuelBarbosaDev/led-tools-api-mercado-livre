import time
import requests
from .config import ML_TIMEOUT, ML_TOKENS_FILE
from .tokens import load_tokens, get_access_token, get_refresh_token
from .oauth import refresh_access_token

def request_json(method, url, **kwargs):
    for _ in range(3):
        tokens = load_tokens(ML_TOKENS_FILE)
        access = get_access_token(tokens)
        headers = kwargs.pop("headers", {})
        if access:
            headers["Authorization"] = f"Bearer {access}"

        r = requests.request(method, url, headers=headers, timeout=ML_TIMEOUT, **kwargs)

        if r.status_code == 401:
            ref = get_refresh_token(tokens)
            if not ref:
                r.raise_for_status()
            refresh_access_token(ref, ML_TOKENS_FILE)
            continue

        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2)
            continue

        r.raise_for_status()
        return r.json()

    raise RuntimeError("Request failed after retries")
