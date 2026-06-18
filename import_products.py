"""
Importacao de produtos historicos -> tabela products (modo batch)
Uso:
    cd backend
    py import_products.py              # importa de verdade
    py import_products.py --dry-run    # so mostra o que seria inserido
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.enums import ProductType

CSV_PATH             = os.path.join(os.path.dirname(__file__), "produtos_historico.csv")
DEFAULT_PRICE        = 0.00
DEFAULT_PRODUCT_TYPE = ProductType.MISC.value


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv", default=CSV_PATH)
    return parser.parse_args()


def parse_number(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_stock(value):
    v = str(value).strip().lower()
    if not v or v == "estoque":
        return 0
    try:
        return max(0, int(v))
    except ValueError:
        return 0


def main():
    args = parse_args()

    if not os.path.exists(args.csv):
        print(f"[ERRO] Arquivo nao encontrado: {args.csv}")
        sys.exit(1)

    rows = []
    skipped = []

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # pula cabecalho
        for line_no, row in enumerate(reader, start=2):
            if not row or not any(r.strip() for r in row):
                continue
            raw_num   = row[0] if len(row) > 0 else ""
            raw_name  = row[1] if len(row) > 1 else ""
            raw_stock = row[2] if len(row) > 2 else ""
            number = parse_number(raw_num)
            name   = str(raw_name).strip()
            stock  = parse_stock(raw_stock)
            if number is None:
                skipped.append((line_no, f"numero invalido: '{raw_num}'"))
                continue
            if not name:
                skipped.append((line_no, f"nome vazio para numero {number}"))
                continue
            rows.append((number, name, stock))

    print(f"[OK] {len(rows)} produtos lidos do CSV")
    if skipped:
        print(f"[AVISO] {len(skipped)} linhas ignoradas (cabecalhos de ano, etc.)")

    if args.dry_run:
        print("\n-- DRY-RUN --")
        for number, name, stock in rows:
            print(f"  #{number:>3}  {name:<50}  estoque: {stock}")
        return

    db = SessionLocal()
    try:
        # Busca todos os numeros que ja existem de uma vez
        print("[DB] Buscando produtos existentes...")
        existing = {
            row[0]
            for row in db.execute(text("SELECT number FROM products")).fetchall()
        }
        print(f"[DB] {len(existing)} produtos ja existem no banco")

        # Filtra apenas os novos
        to_insert = [(n, nm, s) for n, nm, s in rows if n not in existing]
        skipped_count = len(rows) - len(to_insert)

        if not to_insert:
            print("[OK] Nenhum produto novo para inserir.")
            return

        print(f"[DB] Inserindo {len(to_insert)} produtos em batch...")

        # Monta VALUES em batch
        values_sql = ", ".join(
            f"({n}, '{nm.replace(chr(39), chr(39)+chr(39))}', '{DEFAULT_PRODUCT_TYPE}', {DEFAULT_PRICE}, {s}, 0, 0.00)"
            for n, nm, s in to_insert
        )

        db.execute(text(f"""
            INSERT INTO products
                (number, name, product_type, price, stock_quantity, units_sold, revenue)
            VALUES {values_sql}
        """))

        db.commit()
        print(f"\n[DONE] Importacao concluida!")
        print(f"    Inseridos:    {len(to_insert)}")
        print(f"    Ja existiam: {skipped_count}")
        print(f"    Total CSV:   {len(rows)}")
        print(f"\n[DICA] Atualize price e product_type pelo sistema.")

    except Exception as e:
        db.rollback()
        print(f"\n[ERRO] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
