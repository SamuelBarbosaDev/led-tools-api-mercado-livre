#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Renova (refresh) o access_token do Mercado Livre usando refresh_token.

Uso (via env):
  export ML_CLIENT_ID="..."
  export ML_CLIENT_SECRET="..."
  export ML_REFRESH_TOKEN="..."
  python3 ml_refresh_token.py

Opcional:
  export ML_TOKENS_FILE="ml_tokens.json"   # padrão: ml_tokens.json
  export ML_PRINT_EXPORTS="1"             # imprime comandos export úteis

Saída:
- Imprime o JSON de resposta
- Salva/atualiza o arquivo de tokens (inclui o novo refresh_token se vier)
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"ERRO: variável de ambiente {name} não definida.", file=sys.stderr)
        sys.exit(1)
    return val


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    # Enviar no body (x-www-form-urlencoded)
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "ml-oauth-refresh-script/1.0",
    }

    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=timeout)

    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}

        raise RuntimeError(
            "Falha ao renovar token.\n"
            f"HTTP {resp.status_code}\n"
            f"Resposta: {json.dumps(err, ensure_ascii=False, indent=2)}\n\n"
            "Causas comuns:\n"
            "- refresh_token inválido/expirado/revogado\n"
            "- client_id ou client_secret incorretos\n"
        )

    return resp.json()


def load_tokens_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens_file(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def now_utc_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    client_id = require_env("ML_CLIENT_ID")
    client_secret = require_env("ML_CLIENT_SECRET")

    tokens_file = os.getenv("ML_TOKENS_FILE", "ml_tokens.json")
    file_data = load_tokens_file(tokens_file)

    # Você pode passar o refresh_token por env, ou deixar ele no ml_tokens.json (se já tiver)
    env_refresh = os.getenv("ML_REFRESH_TOKEN")
    file_refresh: Optional[str] = None

    # Tentativas comuns de onde o refresh_token pode estar no arquivo
    if isinstance(file_data, dict):
        if isinstance(file_data.get("token"), dict):
            file_refresh = file_data["token"].get("refresh_token")
        if not file_refresh:
            file_refresh = file_data.get("refresh_token")

    refresh_token = env_refresh or file_refresh
    if not refresh_token:
        print(
            "ERRO: ML_REFRESH_TOKEN não definido e não encontrei refresh_token no arquivo.\n"
            f"Defina ML_REFRESH_TOKEN ou coloque o refresh_token em {tokens_file}.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Renovando access_token...")
    token_resp = refresh_access_token(client_id, client_secret, refresh_token)

    # token_resp geralmente contém: access_token, token_type, expires_in, scope, user_id e às vezes refresh_token novo
    obtained_at = now_utc_iso()
    expires_in = int(token_resp.get("expires_in") or 0)
    expires_at = None
    if expires_in > 0:
        expires_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in)
        )

    print("\n=== TOKEN RESPONSE ===")
    print(json.dumps(token_resp, ensure_ascii=False, indent=2))

    # Atualiza arquivo mantendo estrutura parecida com seu ml_get_token.py
    out: Dict[str, Any] = file_data if isinstance(file_data, dict) else {}
    out.setdefault("client_id", client_id)
    out["obtained_at"] = obtained_at
    if expires_at:
        out["expires_at"] = expires_at

    # Salva sempre o token atual em out["token"]
    out["token"] = token_resp

    # IMPORTANTE: refresh token pode rotacionar; se veio um novo, use-o daqui pra frente
    new_refresh = token_resp.get("refresh_token")
    if new_refresh:
        out["refresh_token"] = new_refresh  # campo extra "flat" (facilita)
    else:
        # mantém o anterior em campo flat, se existir
        out["refresh_token"] = refresh_token

    save_tokens_file(tokens_file, out)
    print(f"\nOK! Tokens atualizados em: {tokens_file}")
    if expires_at:
        print(f"Expira em (UTC): {expires_at}")

    if os.getenv("ML_PRINT_EXPORTS") == "1":
        access_token = token_resp.get("access_token", "")
        print("\nComandos úteis:")
        if access_token:
            print(f"  export ML_ACCESS_TOKEN='{access_token}'")
        print(f"  export ML_REFRESH_TOKEN='{out['refresh_token']}'")
        print(f"  python3 export_led_tools_public.py")


if __name__ == "__main__":
    main()
