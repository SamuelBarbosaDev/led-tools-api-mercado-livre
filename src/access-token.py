#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Troca o "authorization code" do Mercado Livre por access_token + refresh_token.

Pré-requisitos:
- Você já tem: APP_ID (client_id), CLIENT_SECRET, CODE, REDIRECT_URI
- CODE é de uso único e expira rápido (se falhar, gere outro pelo fluxo de autorização)
- A redirect_uri DEVE ser exatamente igual à cadastrada no app.

Uso (recomendado via env):
  export ML_CLIENT_ID="..."
  export ML_CLIENT_SECRET="..."
  export ML_CODE="..."
  export ML_REDIRECT_URI="https://samuelbarbosadev.github.io/led-tools-site"
  python3 ml_get_token.py

Ele imprime o JSON completo e opcionalmente salva em ml_tokens.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict

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


def get_access_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
    # A doc recomenda enviar credenciais/parâmetros no BODY (form-urlencoded).
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "ml-oauth-token-script/1.0",
    }

    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=30)

    # Se falhar, tenta imprimir detalhes úteis
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}

        raise RuntimeError(
            "Falha ao obter token.\n"
            f"HTTP {resp.status_code}\n"
            f"Resposta: {json.dumps(err, ensure_ascii=False, indent=2)}\n\n"
            "Causas comuns:\n"
            "- 'code' expirou ou já foi usado (gere outro)\n"
            "- redirect_uri diferente do cadastrado no app (tem que bater 100%)\n"
            "- client_secret/client_id incorretos\n"
        )

    return resp.json()


def main() -> None:
    client_id = require_env("ML_CLIENT_ID")
    client_secret = require_env("ML_CLIENT_SECRET")
    code = require_env("ML_CODE")
    redirect_uri = require_env("ML_REDIRECT_URI")

    print("Solicitando access_token ao Mercado Livre...")
    data = get_access_token(client_id, client_secret, code, redirect_uri)

    # Exemplo de campos esperados: access_token, refresh_token, token_type, expires_in, user_id, scope
    print("\n=== TOKEN RESPONSE ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    out_path = "ml_tokens.json"
    to_save = {
        "obtained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "token": data,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

    print(f"\nOK! Tokens salvos em: {out_path}")
    print("\nPróximo passo:")
    print("  export ML_ACCESS_TOKEN='<access_token>'")
    print("  python3 export_led_tools_public.py")


if __name__ == "__main__":
    main()
