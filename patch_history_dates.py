"""
Corrige o campo changed_at na tabela order_status_history.

O problema: o changed_at ficou com o valor fallback 2014-01-01 12:00:00+00
para todos os pedidos históricos, enquanto a data CORRETA já está em
orders.created_at.

Solução: copiar o created_at de cada pedido para o changed_at do
seu respectivo registro em order_status_history.

Uso:
    cd backend
    py patch_history_dates.py            # aplica a correção
    py patch_history_dates.py --dry-run  # só mostra quantos registros seriam afetados
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sqlalchemy import text
from app.core.database import SessionLocal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Apenas conta, não altera")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Conta quantos registros de histórico têm changed_at diferente do created_at do pedido
        count = db.execute(text("""
            SELECT COUNT(*)
            FROM order_status_history h
            JOIN orders o ON o.id = h.order_id
            WHERE h.changed_at::date != o.created_at::date
        """)).scalar()

        print(f"[INFO] order_status_history: {count} registro(s) com data diferente do pedido")

        if args.dry_run:
            # Mostra amostra
            sample = db.execute(text("""
                SELECT o.number, h.changed_at, o.created_at
                FROM order_status_history h
                JOIN orders o ON o.id = h.order_id
                WHERE h.changed_at::date != o.created_at::date
                ORDER BY o.number
                LIMIT 10
            """)).fetchall()
            if sample:
                print("\n  Amostra (pedido, changed_at atual, created_at correto):")
                for r in sample:
                    print(f"    #{r[0]}  changed_at={str(r[1])[:10]}  ->  correto={str(r[2])[:10]}")
            print("\n[DRY-RUN] Nenhuma alteração feita.")
            return

        if count == 0:
            print("[OK] Todos os registros já estão corretos.")
            return

        # Copia o created_at do pedido para o changed_at do histórico
        updated = db.execute(text("""
            UPDATE order_status_history h
            SET changed_at = o.created_at
            FROM orders o
            WHERE o.id = h.order_id
              AND h.changed_at::date != o.created_at::date
        """)).rowcount

        db.commit()
        print(f"[OK] {updated} registro(s) de order_status_history corrigido(s).")
        print("\n[DONE] Correção aplicada com sucesso!")

    except Exception as e:
        db.rollback()
        print(f"\n[ERRO] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
