# Led.Tools Mercado Livre API

Cliente modular em Python para integração com a API do Mercado Livre, com foco em **listagem de produtos, detalhes de itens e exportação de dados de vendedores**.

O projeto foi projetado para ser:

* Modular
* Fácil de manter
* Pronto para produção
* Simples de expandir (orders, analytics, etc.)
* Usável via CLI  

## Visão Geral

Este projeto fornece uma camada organizada sobre a API do Mercado Livre para:

* Autenticação OAuth2
* Refresh automático de token
* Listagem de itens de vendedores
* Consulta de detalhes de produtos
* Normalização de dados de itens
* Exportação de dados em JSON
* Uso via comandos CLI

Ele separa claramente:

* Lógica de autenticação
* Cliente HTTP
* Cliente Mercado Livre
* Normalização de dados
* Interfaces CLI

## Estrutura do Projeto

```folders
src/
  ledtools_ml/
    config.py
    tokens.py
    oauth.py
    http.py
    ml.py
    normalize.py

  cli/
    ml_get_token.py
    ml_refresh_token.py
    ml_details.py
    export_seller_items.py

requirements.txt
```

## Instalação

### 1) Clonar o repositório

```bash
git clone https://github.com/SamuelBarbosaDev/led-tools-api-mercado-livre.git
cd led-tools-api-mercado-livre
```

### 2) Criar ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate  ## Linux/macOS
.venv\Scripts\activate     ## Windows
```

### 3) Instalar dependências

```bash
pip install -e .
```

Instalação para desenvolvimento (com ferramentas de teste/lint):

```bash
pip install -e ".[dev]"
```

## Configuração

Crie um arquivo `.env`:

```
ML_CLIENT_ID=SEU_CLIENT_ID
ML_CLIENT_SECRET=SEU_CLIENT_SECRET
ML_REDIRECT_URI=SEU_REDIRECT_URI

ML_TOKENS_FILE=ml_tokens.json
ML_SELLER_USER_ID=570565928
ML_SITE_ID=MLB
```

## Fluxo de Autenticação

### 1) Obter authorization code

Abra no navegador:

```
https://auth.mercadolivre.com.br/authorization
 ?response_type=code
 &client_id=SEU_CLIENT_ID
 &redirect_uri=SEU_REDIRECT_URI
```

Após login/autorização, você receberá um `code`.

### 2) Trocar code por token

```bash
ml-get-token SEU_CODE
```

Isso gera `ml_tokens.json` com:

* access_token
* refresh_token
* expires_in

### 3) Refresh de token

Manual:

```bash
ml-refresh-token
```

Automático:

* O projeto faz refresh automaticamente ao receber 401.

## Como Usar

### Exportar itens de um vendedor

```bash
ml-export-seller-items SELLER_ID
```

Exemplo:

```bash
ml-export-seller-items 570565928
```

Gera:

```file
items.json
```

Opcionalmente:

```bash
ml-export-seller-items 570565928 -o meus_itens.json
```

Com campos normalizados:

* id
* title
* price
* sold_quantity
* available_quantity
* permalink
* picture_url
* free_shipping
* logistic_type

### Consultar detalhes de um item

```bash
ml-details MLB123456789
```

Retorna JSON normalizado do item.

## Módulos Internos

### config.py

Centraliza variáveis de ambiente:

* Credenciais
* Timeouts
* Paths
* Configurações do site

Evita hardcode e facilita deploy.

### tokens.py

Responsável por:

* Ler tokens do arquivo
* Salvar tokens
* Extrair access/refresh token

Suporta múltiplos formatos de JSON.

### oauth.py

Implementa OAuth:

* exchange_code_for_token
* refresh_access_token

Isola totalmente a lógica de autenticação.

### http.py

Cliente HTTP robusto:

* Injeta Bearer token automaticamente
* Refresh automático em 401
* Retry em:

  * 429
  * 5xx
* Timeout configurável

É o coração da resiliência do projeto.

### ml.py

Cliente Mercado Livre:

* list_item_ids_public
* list_item_ids_for_user
* get_item

Centraliza endpoints ML.

### normalize.py

Padroniza dados de itens:

* Extrai imagem principal
* Normaliza shipping
* Garante shape consistente

Ideal para analytics.

## Boas Práticas Implementadas

* Separação de responsabilidades
* Código reutilizável
* Refresh automático de token
* Tratamento de rate limit
* Normalização consistente de dados
* Estrutura pronta para escalar
* CLI profissional
* Uso de `pyproject.toml` moderno

## Possíveis Extensões Futuras

O projeto foi pensado para crescer. Exemplos:

### Orders API

* Vendas por período
* Receita
* Status de pedidos

### Analytics

* Dashboard de vendas
* KPIs por categoria
* Histórico de preços

### Performance

* Async (aiohttp)
* Paralelismo
* Cache local

### Data Engineering

* Export para Excel
* Integração com BI
* Pipeline ETL

## Segurança

Nunca commite:

* `.env`
* `ml_tokens.json`
* Credenciais OAuth

Use `.gitignore`.

## Contribuições

Pull requests são bem-vindos.

Sugestões:

* Melhorar cobertura de testes
* Implementar async client
* Adicionar Orders API
* Criar dashboard de exemplo

## Licença

MIT License (ou a que você preferir).
