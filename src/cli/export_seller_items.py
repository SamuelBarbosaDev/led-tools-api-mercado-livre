import argparse, json
from ledtools_ml.ml import list_item_ids_public, get_item
from ledtools_ml.normalize import normalize_item

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("seller_id")
    p.add_argument("-o", "--out", default="items.json")
    args = p.parse_args()

    ids = list_item_ids_public(args.seller_id)
    data = [normalize_item(get_item(i)) for i in ids]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(data)} items to {args.out}")

if __name__ == "__main__":
    main()
