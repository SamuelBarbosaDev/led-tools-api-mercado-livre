#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Busca detalhes de UM item do Mercado Livre via API.
Aceita como entrada um item_id (ex: MLB6052832734) ou uma URL contendo wid=MLB....

Uso:
  python3 ml_item_details.py MLB6052832734
  python3 ml_item_details.py "https://www.mercadolivre.com.br/...&wid=MLB6052832734&..."

Opcional (auth):
  export ML_ACCESS_TOKEN="..."
  python3 ml_item_details.py MLB6052832734

Opcional (refresh automático quando 401):
  - tenha ml_tokens.json (com token.access_token e token.refresh_token e client_id)
  - export ML_CLIENT_SECRET="..."
  python3 ml_item_details.py MLB6052832734
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
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


def parse_item_id(value: str) -> str:
    """
    Aceita:
      - 'MLB6052832734'
      - URL com '?wid=MLB6052832734'
      - qualquer texto contendo 'MLB' + números
    Retorna item_id (MLB##########).
    """
    value = value.strip()

    # Se for URL, tenta pegar wid=
    if value.startswith("http://") or value.startswith("https://"):
        u = urlparse(value)
        qs = parse_qs(u.query)
        wid = qs.get("wid", [None])[0]
        if wid and re.match(r"^MLB\d+$", wid):
            return wid

    # Procura um MLB123 em qualquer lugar
    m = re.search(r"(MLB\d+)", value)
    if m:
        return m.group(1)

    raise ValueError("Não consegui extrair um item_id. Use algo como 'MLB6052832734' ou uma URL com wid=MLB...")


def _headers(cfg: ApiConfig) -> Dict[str, str]:
    h = {
        "Accept": "application/json",
        "User-Agent": "ml-item-details/1.0",
    }
    if cfg.access_token:
        h["Authorization"] = f"Bearer {cfg.access_token}"
    return h


def refresh_access_token(cfg: ApiConfig) -> None:
    """
    Renova access_token usando refresh_token (se configurado).
    """
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
        "User-Agent": "ml-item-details/1.0",
    }

    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=cfg.timeout)
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}
        raise RuntimeError(f"Falha ao renovar token. HTTP {resp.status_code}: {json.dumps(err, ensure_ascii=False)}")

    data = resp.json()
    cfg.access_token = data.get("access_token") or cfg.access_token
    # refresh_token pode rotacionar
    if data.get("refresh_token"):
        cfg.refresh_token = data["refresh_token"]


def request_json(cfg: ApiConfig, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    last_err: Optional[Exception] = None

    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = requests.request(method, url, headers=_headers(cfg), params=params, timeout=cfg.timeout)

            # rate limit / instabilidade
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 30))
                continue

            # token expirou
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


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 ml_item_details.py <ITEM_ID ou URL>", file=sys.stderr)
        sys.exit(2)

    raw_input = sys.argv[1]
    item_id = parse_item_id(raw_input)

    # Token opcional: primeiro tenta env, depois arquivo
    access_env = os.getenv("ML_ACCESS_TOKEN")

    tokens_path = os.getenv("ML_TOKENS_FILE", "ml_tokens.json")
    tokens = load_tokens(tokens_path)
    token_obj = tokens.get("token") if isinstance(tokens.get("token"), dict) else tokens

    cfg = ApiConfig(
        access_token=access_env or token_obj.get("access_token"),
        refresh_token=token_obj.get("refresh_token") or tokens.get("refresh_token"),
        client_id=tokens.get("client_id") or os.getenv("ML_CLIENT_ID"),
        client_secret=os.getenv("ML_CLIENT_SECRET"),
    )

    url = f"{BASE}/items/{item_id}"
    print(f"GET {url}")
    data = request_json(cfg, "GET", url)

    out = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "item": normalize_item(data),
    }

    print("\n=== RESULT (normalizado) ===")
    print(json.dumps(out["item"], ensure_ascii=False, indent=2))

    out_path = f"item_{item_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Se refresh rolou e você quiser persistir o token novo
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
