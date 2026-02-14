#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE = "https://api.mercadolibre.com"
SITE_ID = "MLB"
SELLER_ID = 570565928
TOKEN_URL = f"{BASE}/oauth/token"


@dataclass
class ApiConfig:
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    timeout: int = 30
    max_retries: int = 4
    concurrency: int = 12


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


def _headers(cfg: ApiConfig) -> Dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "led-tools-export/1.1"}
    if cfg.access_token:
        h["Authorization"] = f"Bearer {cfg.access_token}"
    return h


def _is_policy_agent(resp: requests.Response, body_json: Optional[Dict[str, Any]]) -> bool:
    if resp.headers.get("x-policy-agent-block-code"):
        return True
    if isinstance(body_json, dict) and body_json.get("blocked_by") == "PolicyAgent":
        return True
    if isinstance(body_json, dict) and body_json.get("code") == "PA_UNAUTHORIZED_RESULT_FROM_POLICIES":
        return True
    return False


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
        "User-Agent": "led-tools-export/1.1",
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
    for attempt in range(1, cfg.max_retries + 1):
        resp = requests.request(method, url, headers=_headers(cfg), params=params, timeout=cfg.timeout)

        body = None
        try:
            body = resp.json()
        except Exception:
            body = None

        # Fail-fast PolicyAgent
        if resp.status_code in (401, 403) and _is_policy_agent(resp, body):
            raise RuntimeError(
                f"PolicyAgent bloqueou o endpoint.\nURL: {url}\nResposta: {json.dumps(body, ensure_ascii=False)}\n"
                "Isso geralmente exige autorização do vendedor ou liberação do ML para o app."
            )

        # Token expirou -> refresh e tenta de novo
        if resp.status_code == 401 and cfg.refresh_token and cfg.client_secret and cfg.client_id:
            refresh_access_token(cfg)
            continue

        # Rate limit / instabilidade
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2 ** attempt, 20))
            continue

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} em {url}: {body or resp.text}")

        return body if isinstance(body, dict) else {}

    raise RuntimeError(f"Falha após {cfg.max_retries} tentativas: {url}")


def get_me(cfg: ApiConfig) -> Optional[Dict[str, Any]]:
    if not cfg.access_token:
        return None
    return request_json(cfg, "GET", f"{BASE}/users/me")


def list_item_ids_public(cfg: ApiConfig, seller_id: int) -> List[str]:
    item_ids: List[str] = []
    offset = 0
    limit = 50

    while True:
        url = f"{BASE}/sites/{SITE_ID}/search"
        data = request_json(cfg, "GET", url, params={"seller_id": seller_id, "limit": limit, "offset": offset})
        results = data.get("results") or []
        if not results:
            break
        for r in results:
            iid = r.get("id")
            if iid:
                item_ids.append(iid)
        paging = data.get("paging") or {}
        total = int(paging.get("total") or 0)
        offset += len(results)
        if total and offset >= total:
            break
        if len(results) < limit:
            break

    return list(dict.fromkeys(item_ids))


def list_item_ids_seller(cfg: ApiConfig, user_id: int) -> List[str]:
    item_ids: List[str] = []
    offset = 0
    limit = 50

    while True:
        url = f"{BASE}/users/{user_id}/items/search"
        data = request_json(cfg, "GET", url, params={"limit": limit, "offset": offset})
        results = data.get("results") or []
        if not results:
            break
        item_ids.extend([x for x in results if isinstance(x, str)])

        paging = data.get("paging") or {}
        total = int(paging.get("total") or 0)
        offset += len(results)
        if total and offset >= total:
            break
        if len(results) < limit:
            break

    return list(dict.fromkeys(item_ids))


def fetch_item(cfg: ApiConfig, item_id: str) -> Dict[str, Any]:
    return request_json(cfg, "GET", f"{BASE}/items/{item_id}")


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    pics = item.get("pictures") or []
    pic_urls = [p.get("secure_url") or p.get("url") for p in pics if (p.get("secure_url") or p.get("url"))]
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "permalink": item.get("permalink"),
        "seller_id": item.get("seller_id"),
        "category_id": item.get("category_id"),
        "price": item.get("price"),
        "currency_id": item.get("currency_id"),
        "available_quantity": item.get("available_quantity"),
        "sold_quantity": item.get("sold_quantity"),
        "condition": item.get("condition"),
        "thumbnail": item.get("thumbnail"),
        "pictures": pic_urls,
        "last_updated": item.get("last_updated"),
    }


def main() -> None:
    tokens_path = os.getenv("ML_TOKENS_FILE", "ml_tokens.json")
    tokens = load_tokens(tokens_path)
    token_obj = tokens.get("token") if isinstance(tokens.get("token"), dict) else tokens

    cfg = ApiConfig(
        access_token=os.getenv("ML_ACCESS_TOKEN") or (token_obj.get("access_token") if isinstance(token_obj, dict) else None),
        refresh_token=(token_obj.get("refresh_token") if isinstance(token_obj, dict) else None) or tokens.get("refresh_token"),
        client_id=tokens.get("client_id") or os.getenv("ML_CLIENT_ID"),
        client_secret=os.getenv("ML_CLIENT_SECRET"),
    )

    me = None
    try:
        me = get_me(cfg)
    except Exception:
        me = None

    # Escolha automática do modo
    mode = "public"
    if me and me.get("id") == SELLER_ID:
        mode = "seller"

    print(f"Modo selecionado: {mode}")
    if me:
        print(f"Token user_id: {me.get('id')}")

    # Listagem de IDs
    if mode == "seller":
        item_ids = list_item_ids_seller(cfg, SELLER_ID)
    else:
        item_ids = list_item_ids_public(cfg, SELLER_ID)

    print(f"Encontrados {len(item_ids)} itens.")

    # Detalhes item-a-item️
    out_items: List[Dict[str, Any]] = []
    errors: List[Tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as ex:
        futs = {ex.submit(fetch_item, cfg, iid): iid for iid in item_ids}
        for i, fut in enumerate(as_completed(futs), start=1):
            iid = futs[fut]
            try:
                out_items.append(normalize_item(fut.result()))
            except Exception as e:
                errors.append((iid, str(e)))
            if i % 50 == 0 or i == len(item_ids):
                print(f"  progresso: {i}/{len(item_ids)}")

    # Persistir tokens caso refresh rotacione
    if tokens and isinstance(token_obj, dict) and cfg.access_token:
        token_obj["access_token"] = cfg.access_token
        if cfg.refresh_token:
            token_obj["refresh_token"] = cfg.refresh_token
        tokens["token"] = token_obj
        tokens["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_tokens(tokens_path, tokens)

    payload = {
        "source": {
            "seller_id": SELLER_ID,
            "mode": mode,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "count": len(out_items),
        "items": sorted(out_items, key=lambda x: (x.get("id") or "")),
        "errors": [{"item_id": iid, "error": err} for iid, err in errors],
    }

    out_path = "led_tools_public_items.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nOK! Salvo em: {out_path}")
    if errors:
        print(f"Atenção: {len(errors)} falharam. Veja 'errors' no JSON.")


if __name__ == "__main__":
    main()
