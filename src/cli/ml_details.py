import argparse, json
from ledtools_ml.ml import get_item
from ledtools_ml.normalize import normalize_item

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("item_id")
    args = p.parse_args()
    it = get_item(args.item_id)
    print(json.dumps(normalize_item(it), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
