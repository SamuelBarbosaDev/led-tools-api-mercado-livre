import argparse
from ledtools_ml.oauth import exchange_code_for_token
from ledtools_ml.config import ML_TOKENS_FILE

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("code")
    args = parser.parse_args()
    print(exchange_code_for_token(args.code, ML_TOKENS_FILE))

if __name__ == "__main__":
    main()
