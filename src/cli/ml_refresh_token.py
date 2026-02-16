from ledtools_ml.tokens import load_tokens, get_refresh_token
from ledtools_ml.oauth import refresh_access_token
from ledtools_ml.config import ML_TOKENS_FILE

def main() -> None:
    t = load_tokens(ML_TOKENS_FILE)
    rt = get_refresh_token(t)
    if not rt:
        raise SystemExit("Refresh token não encontrado em ml_tokens.json")
    print(refresh_access_token(rt, ML_TOKENS_FILE))

if __name__ == "__main__":
    main()
