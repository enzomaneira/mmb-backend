# Brinquedos da Mãe — Backend

API em Python (FastAPI) para gestão de clientes, produtos, pedidos, estoque, receita e gráficos.

## Requisitos

- Python 3.12+
- PostgreSQL 16+

## Setup local

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Suba o banco com Docker (na raiz do projeto):

```bash
docker compose up db -d
```

Rode as migrações e a API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

A documentação interativa fica em [http://localhost:8000/docs](http://localhost:8000/docs).

## Setup com Docker (API + banco)

Na raiz do projeto:

```bash
docker compose up --build
```

## Endpoints principais

| Recurso | Prefixo |
|---------|---------|
| Clientes | `/api/v1/customers` |
| Produtos | `/api/v1/products` |
| Pedidos | `/api/v1/orders` |
| Receita | `/api/v1/revenue` |
| Gráficos | `/api/v1/charts` |

## Regras de negócio

- Ao mudar um pedido para `PAID`, os contadores de cliente e produto são atualizados e a receita mensal é incrementada.
- Ao remover um pedido pago ou reverter o status de `PAID`, os contadores são ajustados.
- Cada mudança de status registra data em `order_status_history`.
