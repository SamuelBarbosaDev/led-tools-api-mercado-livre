#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Busca detalhes de UM recurso do Mercado Livre via API:
- Item (listing): /items/{ITEM_ID}   ex: MLB6052832734
- Produto (catálogo): /products/{PRODUCT_ID}  ex: MLB63161789

Entrada aceita:
- "MLB123..." (id)
- URL do ML contendo wid=MLB... (item_id)
- URL do ML contendo /p/MLB... (product_id)
- Qualquer texto contendo MLB\d+

Uso:
  python3 ml_details.py MLB6052832734
  python3 ml_details.py MLB63161789
  python3 ml_details.py "https://www.mercadolivre.com.br/...&wid=MLB6052832734..."
  python3 ml_details.py "https://www.mercadolivre.com.br/.../p/MLB63161789?..."

Auth:
- Opcional: export ML_ACCESS_TOKEN="..."
- Opcional (refresh automático em 401): ter ml_tokens.json + export ML_CLIENT_SECRET="..."

Observação:
- No seu ambiente atual, /items pode retornar 403 PolicyAgent para terceiros.
  Este script só "tenta" e mostra o erro; fica pronto para quando estiver liberado.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests

BASE = "https://api.mercadolibre.com"
TOKEN_URL = f"{BASE}/oauth/token"


@dataclass
class ApiConfig:
    access_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    timeout: int = 30
    max_retries: int = 5


def load_tokens(path: str = "ml_tokens.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse_input(value: str) -> Tuple[str, str]:
    """
    Retorna (kind, id), onde kind é "item" ou "product".

    Regras:
    - Se URL tiver wid=MLB..., é ITEM
    - Se URL tiver /p/MLB..., é PRODUCT
    - Se só tiver MLB\d+, decide por default como ITEM, mas o script tenta fallback para PRODUCT.
    """
    value = value.strip()

    if value.startswith("http://") or value.startswith("https://"):
        u = urlparse(value)
        qs = parse_qs(u.query)

        wid = qs.get("wid", [None])[0]
        if wid and re.match(r"^MLB\d+$", wid):
            return ("item", wid)

        # detecta /p/MLB123...
        mprod = re.search(r"/p/(MLB\d+)", u.path)
        if mprod:
            return ("product", mprod.group(1))

    mid = re.search(r"(MLB\d+)", value)
    if mid:
        # default: item (pois é o mais comum para /items/{id})
        return ("item", mid.group(1))

    raise ValueError("Não consegui extrair um ID MLB. Use um ID (MLB...) ou uma URL com wid= ou /p/.")


def _headers(cfg: ApiConfig) -> Dict[str, str]:
    h = {
        "Accept": "application/json",
        "User-Agent": "ml-details/1.0",
    }
    if cfg.access_token:
        h["Authorization"] = f"Bearer {cfg.access_token}"
    return h


def refresh_access_token(cfg: ApiConfig) -> None:
    if not (cfg.client_id and cfg.client_secret and cfg.refresh_token):
        raise RuntimeError("Refresh não configurado (faltam client_id/client_secret/refresh_token).")

    payload = {
        "grant_type": "refresh_token",
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "refresh_token": cfg.refresh_token,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "ml-details/1.0",
    }
    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=cfg.timeout)
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}
        raise RuntimeError(f"Falha ao renovar token. HTTP {resp.status_code}: {json.dumps(err, ensure_ascii=False)}")

    data = resp.json()
    if data.get("access_token"):
        cfg.access_token = data["access_token"]
    if data.get("refresh_token"):
        cfg.refresh_token = data["refresh_token"]  # rotação


def request_json(cfg: ApiConfig, url: str) -> Dict[str, Any]:
    last_err: Optional[Exception] = None

    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = requests.get(url, headers=_headers(cfg), timeout=cfg.timeout)

            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 30))
                continue

            if resp.status_code == 401 and cfg.refresh_token and cfg.client_secret and cfg.client_id:
                refresh_access_token(cfg)
                continue

            if resp.status_code >= 400:
                try:
                    err = resp.json()
                except Exception:
                    err = {"raw": resp.text}
                raise RuntimeError(f"HTTP {resp.status_code} em {url}: {json.dumps(err, ensure_ascii=False)}")

            return resp.json()

        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))

    raise RuntimeError(f"Falha após retries: {last_err}")


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    pics = item.get("pictures") or []
    pic_urls = [p.get("secure_url") or p.get("url") for p in pics if (p.get("secure_url") or p.get("url"))]

    return {
        "kind": "item",
        "id": item.get("id"),
        "title": item.get("title"),
        "permalink": item.get("permalink"),
        "status": item.get("status"),
        "site_id": item.get("site_id"),
        "seller_id": item.get("seller_id"),
        "category_id": item.get("category_id"),
        "price": item.get("price"),
        "currency_id": item.get("currency_id"),
        "original_price": item.get("original_price"),
        "available_quantity": item.get("available_quantity"),
        "sold_quantity": item.get("sold_quantity"),
        "condition": item.get("condition"),
        "listing_type_id": item.get("listing_type_id"),
        "thumbnail": item.get("thumbnail"),
        "pictures": pic_urls,
        "attributes": [
            {"id": a.get("id"), "name": a.get("name"), "value_name": a.get("value_name")}
            for a in (item.get("attributes") or [])
        ],
        "date_created": item.get("date_created"),
        "last_updated": item.get("last_updated"),
    }


def normalize_product(prod: Dict[str, Any]) -> Dict[str, Any]:
    # Estruturas de /products podem variar; mantemos o básico e campos úteis.
    pics = prod.get("pictures") or []
    pic_urls = [p.get("secure_url") or p.get("url") for p in pics if (p.get("secure_url") or p.get("url"))]

    return {
        "kind": "product",
        "id": prod.get("id"),
        "name": prod.get("name") or prod.get("title"),
        "buy_box_winner": prod.get("buy_box_winner"),
        "domain_id": prod.get("domain_id"),
        "category_id": prod.get("category_id"),
        "pictures": pic_urls,
        "attributes": [
            {"id": a.get("id"), "name": a.get("name"), "value_name": a.get("value_name")}
            for a in (prod.get("attributes") or [])
        ],
        "status": prod.get("status"),
        "date_created": prod.get("date_created"),
        "last_updated": prod.get("last_updated"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 ml_details.py <ITEM_ID/PRODUCT_ID ou URL>", file=sys.stderr)
        sys.exit(2)

    kind_hint, ml_id = parse_input(sys.argv[1])

    # Config auth (opcional)
    tokens_path = os.getenv("ML_TOKENS_FILE", "ml_tokens.json")
    tokens = load_tokens(tokens_path)
    token_obj = tokens.get("token") if isinstance(tokens.get("token"), dict) else tokens

    cfg = ApiConfig(
        access_token=os.getenv("ML_ACCESS_TOKEN") or (token_obj.get("access_token") if isinstance(token_obj, dict) else None),
        refresh_token=(token_obj.get("refresh_token") if isinstance(token_obj, dict) else None) or tokens.get("refresh_token"),
        client_id=tokens.get("client_id") or os.getenv("ML_CLIENT_ID"),
        client_secret=os.getenv("ML_CLIENT_SECRET"),
    )

    tried: list[str] = []
    fetched: Dict[str, Any] = {}
    used_kind: Optional[str] = None
    err_last: Optional[Exception] = None

    # Tentativa 1: respeita o hint (item ou product)
    # Tentativa 2: fallback (o outro tipo)
    kinds_to_try = [kind_hint, "product" if kind_hint == "item" else "item"]

    for k in kinds_to_try:
        tried.append(k)
        url = f"{BASE}/items/{ml_id}" if k == "item" else f"{BASE}/products/{ml_id}"
        print(f"GET {url}")
        try:
            fetched = request_json(cfg, url)
            used_kind = k
            break
        except Exception as e:
            err_last = e
            print(f"Falhou em {k}: {e}\n")

    if used_kind is None:
        raise SystemExit(
            "Não consegui obter dados.\n"
            f"Tentei: {tried}\n"
            f"Último erro: {err_last}"
        )

    # Normaliza e salva
    if used_kind == "item":
        norm = normalize_item(fetched)
        out_path = f"item_{ml_id}.json"
    else:
        norm = normalize_product(fetched)
        out_path = f"product_{ml_id}.json"

    out = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tried": tried,
        "result": norm,
    }

    print("\n=== RESULT (normalizado) ===")
    print(json.dumps(norm, ensure_ascii=False, indent=2))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Persistência opcional caso refresh rotacione
    if tokens and isinstance(token_obj, dict) and cfg.access_token:
        token_obj["access_token"] = cfg.access_token
        if cfg.refresh_token:
            token_obj["refresh_token"] = cfg.refresh_token
        tokens["token"] = token_obj
        tokens["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_tokens(tokens_path, tokens)

    print(f"\nOK! Salvo em: {out_path}")


if __name__ == "__main__":
    main()
