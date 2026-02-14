# led-tools-api-mercado-livre

Integração em Python com a API do Mercado Livre focada na loja **Led.Tools**, incluindo:

- Autenticação OAuth2 (authorization code + refresh token)
- Scripts para obtenção e renovação de tokens
- Consulta de detalhes de produtos
- Exportação de dados de anúncios
- Base para analytics de marketplace

Este projeto foi criado para estudar e utilizar a API oficial do Mercado Livre em cenários reais de e-commerce.

## Objetivo do projeto

Este repositório tem como finalidade:

- Aprender na prática a API do Mercado Livre
- Construir uma base de coleta de dados para analytics
- Automatizar consultas de anúncios e produtos
- Preparar infraestrutura para uso futuro com a Led.Tools

## Estrutura do projeto

```output

.
├── README.md
└── src
├── access-token.py
├── export_led_tools_public.py
├── list_ledtools_items.py
├── ml_details.py
├── ml_item_details.py
├── ml_refresh_token.py
├── ml_tokens.json
└── requirements.txt

```

### Descrição dos scripts

### `access-token.py`

Troca o `authorization_code` por:

- access_token  
- refresh_token  

Primeiro passo após autorizar o app no Mercado Livre.

### `ml_refresh_token.py`

Renova automaticamente o access token usando:

```output

grant_type=refresh_token

```

Essencial para manter a integração funcionando sem novo login.

### `ml_tokens.json`
Armazena:

- access_token
- refresh_token
- expires_in
- metadados do token

Nunca deve ser commitado com tokens reais.

### `export_led_tools_public.py`

Script de exportação de anúncios.

Possui:

- paginação
- retries
- normalização de dados
- detecção de PolicyAgent
- modo público vs modo seller

### `list_ledtools_items.py`

Lista anúncios da conta do vendedor via:

```output

/users/{USER_ID}/items/search

```

Requer token autorizado pelo vendedor.

### `ml_item_details.py`

Consulta detalhes de um único anúncio via:

```output

/items/{ITEM_ID}

```

Aceita:

- ID direto
- URL do Mercado Livre

### `ml_details.py`

Script flexível que detecta automaticamente:

- item (listing)
- product (catálogo)

E chama:

```output

/items/{id}
/products/{id}

```

## Instalação

Clone o repositório:

```bash
git clone https://github.com/SamuelBarbosaDev/led-tools-api-mercado-livre.git
cd led-tools-api-mercado-livre/src
````

Instale dependências:

```bash
pip install -r requirements.txt
```

## Configuração OAuth

1. Crie um app no Mercado Livre Developers
2. Configure uma Redirect URI
3. Gere o authorization code
4. Execute:

    ```bash
    python access-token.py
    ```

5. Tokens serão salvos em `ml_tokens.json`

## Renovar token

```bash
python ml_refresh_token.py
```

## Exemplos de uso

### Detalhes de um produto

```bash
python ml_item_details.py MLB123456789
```

ou

```bash
python ml_item_details.py "https://produto.mercadolivre.com.br/..."
```

### Exportar anúncios

```bash
python export_led_tools_public.py
```

## Limitações importantes da API

A API do Mercado Livre possui restrições de acesso.

Endpoints como:

```output
/sites/MLB/search
/items/{id}
/users/{id}/items/search
```

podem retornar:

```output
403 - blocked_by: PolicyAgent
```

Isso significa:

* O recurso está bloqueado por política interna do Mercado Livre
* Nem sempre depende de token ou escopo
* Pode exigir autorização do vendedor ou liberação do app

Este projeto já trata esses cenários e falha de forma explícita.

## Aprendizados com este projeto

* OAuth2 completo na prática
* Rotação de refresh token
* Tratamento de rate limit e retries
* Diagnóstico de erros 401 vs 403
* Limitações reais de APIs de marketplace
* Estruturação de coletores de dados

## Uso futuro com a Led.Tools

Quando a Led.Tools autorizar o app:

* Será possível listar anúncios da conta
* Acessar dados de vendas
* Construir analytics completos
* Automatizar monitoramento de catálogo

## Segurança

Nunca exponha:

* client_secret
* access_token
* refresh_token

Adicione ao `.gitignore`:

```
ml_tokens.json
.env
```
