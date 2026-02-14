#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exporta dados públicos dos anúncios da loja Led Tools (Mercado Livre).

Fonte dos itens:
- /sites/MLB/search?seller_id=... (Items & Searches)

Enriquecimento:
- /items/{id} (detalhes do item/anúncio)

Saída:
- led_tools_public_items.json

Opcional:
- Se algum endpoint retornar 401/403, defina ML_ACCESS_TOKEN no ambiente
  (Bearer token OAuth) e o script tenta novamente com autorização.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

load_dotenv()


BASE = "https://api.mercadolibre.com"
SITE_ID = "MLB"
SELLER_ID = 570565928  # Led Tools (obtido do link público da loja)


@dataclass
class ApiConfig:
    access_token: Optional[str] = None
    timeout: int = 30
    max_retries: int = 5
    concurrency: int = 16


def _headers(cfg: ApiConfig) -> Dict[str, str]:
    h = {
        "Accept": "application/json",
        "User-Agent": "led-tools-public-export/1.0",
    }
    if cfg.access_token:
        h["Authorization"] = f"Bearer {cfg.access_token}"
    return h


def _request_json(
    cfg: ApiConfig,
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Request com retries simples (429/5xx) e fallback para token se disponível.
    """
    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = requests.request(
                method,
                url,
                headers=_headers(cfg),
                params=params,
                timeout=cfg.timeout,
            )

            print("="*50)
            print(resp)

            # Rate limit / instabilidade temporária
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue

            # Erros de auth (tenta explicar no erro)
            if resp.status_code in (401, 403):
                raise RuntimeError(
                    f"HTTP {resp.status_code} em {url}. "
                    f"Se você não setou ML_ACCESS_TOKEN, talvez este endpoint esteja exigindo OAuth."
                )

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            if attempt == cfg.max_retries:
                raise
            time.sleep(min(2 ** attempt, 30))
        except RuntimeError:
            # Não adianta retry infinito em 401/403 sem token
            raise

    raise RuntimeError("Falha inesperada no request (retries esgotados).")


def list_item_ids_by_seller(cfg: ApiConfig, seller_id: int) -> List[str]:
    """
    Pagina pela busca do vendedor e retorna lista de item_ids.
    Endpoint: /sites/MLB/search?seller_id=SELLER_ID
    """
    item_ids: List[str] = []
    offset = 0
    limit = 50  # limite usual; se o ML reduzir, a API retorna menos e seguimos paginando

    while True:
        url = f"{BASE}/sites/{SITE_ID}/search"
        data = _request_json(cfg, "GET", url, params={"seller_id": seller_id, "limit": limit, "offset": offset})

        results = data.get("results", [])
        if not results:
            break

        # Cada result costuma ter "id"
        for r in results:
            rid = r.get("id")
            if rid:
                item_ids.append(rid)

        paging = data.get("paging", {}) or {}
        total = int(paging.get("total", 0) or 0)

        offset += len(results)
        if offset >= total:
            break

    # remove duplicados preservando ordem
    seen = set()
    dedup = []
    for x in item_ids:
        if x not in seen:
            seen.add(x)
            dedup.append(x)

    return dedup


def fetch_item_detail(cfg: ApiConfig, item_id: str) -> Dict[str, Any]:
    """
    Busca detalhes públicos do item: /items/{id}
    """
    url = f"{BASE}/items/{item_id}"
    return _request_json(cfg, "GET", url)


def normalize_item_public_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai um "shape" estável com campos públicos úteis para analytics.
    """
    pictures = item.get("pictures") or []
    picture_urls = [p.get("secure_url") or p.get("url") for p in pictures if (p.get("secure_url") or p.get("url"))]

    shipping = item.get("shipping") or {}
    seller_address = item.get("seller_address") or {}
    location = {
        "city": (seller_address.get("city") or {}).get("name"),
        "state": (seller_address.get("state") or {}).get("name"),
        "country": (seller_address.get("country") or {}).get("name"),
    }

    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "permalink": item.get("permalink"),
        "status": item.get("status"),
        "condition": item.get("condition"),
        "site_id": item.get("site_id"),
        "category_id": item.get("category_id"),
        "seller_id": item.get("seller_id"),
        "price": item.get("price"),
        "currency_id": item.get("currency_id"),
        "original_price": item.get("original_price"),
        "available_quantity": item.get("available_quantity"),
        "sold_quantity": item.get("sold_quantity"),
        "listing_type_id": item.get("listing_type_id"),
        "catalog_product_id": item.get("catalog_product_id"),
        "thumbnail": item.get("thumbnail"),
        "pictures": picture_urls,
        "attributes": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "value_name": a.get("value_name"),
            }
            for a in (item.get("attributes") or [])
        ],
        "shipping": {
            "mode": shipping.get("mode"),
            "free_shipping": shipping.get("free_shipping"),
            "logistic_type": shipping.get("logistic_type"),
            "store_pick_up": shipping.get("store_pick_up"),
        },
        "seller_location": location,
        "date_created": item.get("date_created"),
        "last_updated": item.get("last_updated"),
    }


def main() -> None:
    token = os.getenv("ML_ACCESS_TOKEN")  # opcional
    cfg = ApiConfig(access_token=token)

    print(f"Seller: {SELLER_ID} | Token: {'SIM' if bool(token) else 'NÃO'}")
    print("Listando anúncios do vendedor...")
    item_ids = list_item_ids_by_seller(cfg, SELLER_ID)
    print(f"Encontrados {len(item_ids)} anúncios.")

    print("Baixando detalhes públicos de cada anúncio...")
    items_out: List[Dict[str, Any]] = []
    errors: List[Tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as ex:
        fut_map = {ex.submit(fetch_item_detail, cfg, item_id): item_id for item_id in item_ids}
        for i, fut in enumerate(as_completed(fut_map), start=1):
            item_id = fut_map[fut]
            try:
                raw = fut.result()
                items_out.append(normalize_item_public_fields(raw))
            except Exception as e:
                errors.append((item_id, str(e)))

            if i % 50 == 0 or i == len(item_ids):
                print(f"  progresso: {i}/{len(item_ids)}")

    items_out.sort(key=lambda x: (x.get("id") or ""))

    out = {
        "source": {
            "site_id": SITE_ID,
            "seller_id": SELLER_ID,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "token_used": bool(token),
        },
        "count": len(items_out),
        "items": items_out,
        "errors": [{"item_id": iid, "error": err} for iid, err in errors],
    }

    out_path = "led_tools_public_items.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\nOK! Salvo em: {out_path}")
    if errors:
        print(f"Atenção: {len(errors)} itens falharam. Veja a chave 'errors' no JSON.")


if __name__ == "__main__":
    main()
