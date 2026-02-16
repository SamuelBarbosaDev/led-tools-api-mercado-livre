import json
from pathlib import Path

def load_tokens(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save_tokens(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_access_token(tokens: dict):
    if "access_token" in tokens:
        return tokens["access_token"]
    if "token" in tokens and isinstance(tokens["token"], dict):
        return tokens["token"].get("access_token")
    return None

def get_refresh_token(tokens: dict):
    if "refresh_token" in tokens:
        return tokens["refresh_token"]
    if "token" in tokens and isinstance(tokens["token"], dict):
        return tokens["token"].get("refresh_token")
    return None
