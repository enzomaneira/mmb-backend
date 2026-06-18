"""
Importação de clientes históricos → tabela customers
=====================================================
Uso:
    cd backend
    python import_customers.py              # importa de verdade
    python import_customers.py --dry-run    # só mostra o que seria inserido

O CSV deve estar em: backend/clientes_historico.csv
Formato esperado:
    coluna 0 → número do cliente (inteiro)
    coluna 1 → nome do cliente
    (demais colunas são ignoradas)
    linha 1  → cabeçalho (ignorada)
"""

import argparse
import csv
import os
import sys

# ── garante que o módulo `app` seja encontrado quando rodado de backend/ ──
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.customer import Customer

CSV_PATH = os.path.join(os.path.dirname(__file__), "clientes_historico.csv")


def parse_args():
    parser = argparse.ArgumentParser(description="Importa clientes de um CSV para o banco.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas lista o que seria inserido, sem gravar.")
    parser.add_argument("--csv", default=CSV_PATH, help=f"Caminho do CSV (padrão: {CSV_PATH})")
    return parser.parse_args()


def parse_number(value: str) -> int | None:
    """Tenta converter a coluna número para inteiro."""
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def clean_name(value: str) -> str:
    """Remove espaços extras e caracteres invisíveis."""
    return str(value).strip()


def main():
    args = parse_args()

    if not os.path.exists(args.csv):
        print(f"❌  Arquivo não encontrado: {args.csv}")
        print("    Salve o CSV como 'clientes_historico.csv' na pasta backend/ e tente novamente.")
        sys.exit(1)

    # ── lê o CSV ──────────────────────────────────────────────────────────────
    rows: list[tuple[int, str]] = []   # (number, name)
    skipped: list[tuple[int, str]] = []

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # pula cabeçalho
        print(f"📄  Cabeçalho detectado: {header}")

        for line_no, row in enumerate(reader, start=2):
            if not row or not any(row):
                continue  # linha vazia

            raw_num  = row[0] if len(row) > 0 else ""
            raw_name = row[1] if len(row) > 1 else ""

            number = parse_number(raw_num)
            name   = clean_name(raw_name)

            if number is None:
                skipped.append((line_no, f"número inválido: '{raw_num}' | nome: '{raw_name}'"))
                continue
            if not name:
                skipped.append((line_no, f"nome vazio para número {number}"))
                continue

            rows.append((number, name))

    print(f"\n✅  {len(rows)} clientes prontos para importar")
    if skipped:
        print(f"⚠️   {len(skipped)} linha(s) ignorada(s):")
        for ln, reason in skipped:
            print(f"     linha {ln}: {reason}")

    if args.dry_run:
        print("\n── DRY-RUN: nenhum dado será gravado ──")
        for number, name in rows:
            print(f"  #{number:>3}  {name}")
        return

    # ── insere no banco ───────────────────────────────────────────────────────
    db = SessionLocal()
    try:
        inserted = 0
        already_exists = 0

        for number, name in rows:
            exists = db.query(Customer).filter(Customer.number == number).first()
            if exists:
                already_exists += 1
                print(f"  ⏭️  Já existe  #{number} — {exists.name}")
                continue

            customer = Customer(number=number, name=name)
            db.add(customer)
            inserted += 1
            print(f"  ➕  Inserindo  #{number} — {name}")

        db.commit()
        print(f"\n🎉  Importação concluída!")
        print(f"    Inseridos:       {inserted}")
        print(f"    Já existiam:     {already_exists}")
        print(f"    Total no CSV:    {len(rows)}")

    except Exception as e:
        db.rollback()
        print(f"\n❌  Erro ao gravar no banco: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
