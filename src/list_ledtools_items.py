#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lista e exporta itens (publicações) de um vendedor via API do Mercado Livre, item por item,
no estilo "exporter" com paginação, retries e refresh automático do token.

IMPORTANTE:
- /users/{USER_ID}/items/search exige token emitido para esse USER_ID (conta do vendedor).
  Então, para a led.tools, o token precisa ser autorizado pela conta 570565928.

Docs:
- Items & Searches: /users/$USER_ID/items/search e /items/{id}
- OAuth: refresh_token flow (/oauth/token)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE = "https://api.mercadolibre.com"
TOKEN_URL = f"{BASE}/oauth/token"

DEFAULT_USER_ID = 570565928  # led.tools


@dataclass
class ApiConfig:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    timeout: int = 30
    max_retries: int = 5
    concurrency: int = 12


def load_tokens(path: str = "ml_tokens.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de tokens não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _auth_headers(cfg: ApiConfig) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {cfg.access_token}",
        "User-Agent": "led-tools-items-export/1.0",
    }


def refresh_access_token(cfg: ApiConfig) -> Dict[str, Any]:
    """
    Renova o access_token usando refresh_token.
    """
    payload = {
        "grant_type": "refresh_token",
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "refresh_token": cfg.refresh_token,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "led-tools-items-export/1.0",
    }
    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=cfg.timeout)
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}
        raise RuntimeError(f"Falha ao renovar token. HTTP {resp.status_code}: {json.dumps(err, ensure_ascii=False)}")
    return resp.json()


def _request_json(cfg: ApiConfig, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Request com:
    - retries para 429/5xx
    - refresh automático em 401 (token expirou)
    """
    last_err: Optional[Exception] = None

    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = requests.request(
                method,
                url,
                headers=_auth_headers(cfg),
                params=params,
                timeout=cfg.timeout,
            )

            # Rate limit / instabilidades
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 30))
                continue

            # Token expirou
            if resp.status_code == 401:
                token_data = refresh_access_token(cfg)
                cfg.access_token = token_data["access_token"]

                # refresh_token pode rotacionar
                if "refresh_token" in token_data and token_data["refresh_token"]:
                    cfg.refresh_token = token_data["refresh_token"]

                # tenta de novo imediatamente (sem consumir tentativa extra)
                continue

            # Policy / forbidden (não adianta retry infinito)
            if resp.status_code == 403:
                try:
                    err = resp.json()
                except Exception:
                    err = {"raw": resp.text}
                raise RuntimeError(f"403 Policy/Forbidden em {url}: {json.dumps(err, ensure_ascii=False)}")

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            last_err = e
            # para erros não “recuperáveis” (403 RuntimeError), estoura
            if isinstance(e, RuntimeError) and "403" in str(e):
                raise
            time.sleep(min(2 ** attempt, 30))

    raise RuntimeError(f"Falha após retries: {last_err}")


def list_item_ids_for_user(cfg: ApiConfig, user_id: int) -> List[str]:
    """
    Lista IDs via /users/{USER_ID}/items/search com paginação por 'offset' (se suportado).
    Alguns ambientes retornam um payload com 'results' (lista de item_ids).
    """
    item_ids: List[str] = []
    offset = 0
    limit = 50

    while True:
        url = f"{BASE}/users/{user_id}/items/search"
        data = _request_json(cfg, "GET", url, params={"limit": limit, "offset": offset})

        results = data.get("results") or []
        if not results:
            break

        # results costuma ser lista de IDs (strings)
        item_ids.extend([x for x in results if isinstance(x, str)])

        paging = data.get("paging") or {}
        total = int(paging.get("total") or 0)
        offset += len(results)

        if total and offset >= total:
            break

        # fallback: se não vier total, para quando página vier menor que limit
        if len(results) < limit:
            break

    # dedup preservando ordem
    seen = set()
    dedup: List[str] = []
    for iid in item_ids:
        if iid not in seen:
            seen.add(iid)
            dedup.append(iid)

    return dedup


def fetch_item_detail(cfg: ApiConfig, item_id: str) -> Dict[str, Any]:
    url = f"{BASE}/items/{item_id}"
    return _request_json(cfg, "GET", url)


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    pics = item.get("pictures") or []
    pic_urls = [p.get("secure_url") or p.get("url") for p in pics if (p.get("secure_url") or p.get("url"))]

    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "permalink": item.get("permalink"),
        "status": item.get("status"),
        "seller_id": item.get("seller_id"),
        "site_id": item.get("site_id"),
        "category_id": item.get("category_id"),
        "price": item.get("price"),
        "currency_id": item.get("currency_id"),
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
    tokens_path = os.getenv("ML_TOKENS_FILE", "ml_tokens.json")
    tokens = load_tokens(tokens_path)

    # Aceita os dois formatos mais comuns que você já vem usando
    token_obj = tokens.get("token") if isinstance(tokens.get("token"), dict) else tokens

    client_id = tokens.get("client_id") or os.getenv("ML_CLIENT_ID")
    client_secret = os.getenv("ML_CLIENT_SECRET")  # não recomendo salvar no json
    access_token = token_obj.get("access_token")
    refresh_token = token_obj.get("refresh_token") or tokens.get("refresh_token")

    if not client_id or not client_secret or not access_token or not refresh_token:
        raise SystemExit(
            "Faltam variáveis/credenciais.\n"
            "Defina ML_CLIENT_SECRET e tenha ml_tokens.json com access_token/refresh_token e client_id.\n"
            "Env opcional: ML_CLIENT_ID, ML_TOKENS_FILE."
        )

    user_id = int(os.getenv("ML_SELLER_USER_ID", str(DEFAULT_USER_ID)))

    cfg = ApiConfig(
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    print(f"Listando itens do user_id={user_id} ...")
    item_ids = list_item_ids_for_user(cfg, user_id)
    print(f"Encontrados {len(item_ids)} item_ids.")

    if not item_ids:
        print("Nenhum item retornado. Se você ainda não tem autorização da led.tools, isso é esperado.")
        return

    print("Buscando detalhes item-a-item...")
    out_items: List[Dict[str, Any]] = []
    errors: List[Tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as ex:
        futs = {ex.submit(fetch_item_detail, cfg, iid): iid for iid in item_ids}
        for idx, fut in enumerate(as_completed(futs), start=1):
            iid = futs[fut]
            try:
                raw = fut.result()
                out_items.append(normalize_item(raw))
            except Exception as e:
                errors.append((iid, str(e)))

            if idx % 50 == 0 or idx == len(item_ids):
                print(f"  progresso: {idx}/{len(item_ids)}")

    # Atualiza o arquivo de tokens se refresh rotacionou
    token_obj["access_token"] = cfg.access_token
    token_obj["refresh_token"] = cfg.refresh_token
    tokens["token"] = token_obj
    tokens["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_tokens(tokens_path, tokens)

    payload = {
        "source": {
            "user_id": user_id,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "count": len(out_items),
        "items": sorted(out_items, key=lambda x: (x.get("id") or "")),
        "errors": [{"item_id": iid, "error": err} for iid, err in errors],
    }

    out_path = "led_tools_items_detailed.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nOK! Salvo em: {out_path}")
    if errors:
        print(f"Atenção: {len(errors)} falharam. Veja 'errors' no JSON.")


if __name__ == "__main__":
    main()
