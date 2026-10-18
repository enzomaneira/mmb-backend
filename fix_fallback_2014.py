"""
Corrige os pedidos que ficaram com a data falsa 2014-01-01 (fallback do
import_orders.py para pedidos sem data na planilha).

Para cada pedido com created_at = 2014-01-01:
  - PAID do histórico      -> data de DELIVERED (pagamento quase sempre é na entrega);
                              sem DELIVERED, usa a data real mais recente do histórico
                              (só para pedidos PAID; cancelados ficam para revisão manual)
  - created_at do pedido   -> data real mais antiga do histórico
  - outros status em 2014  -> o novo created_at

Pedidos sem nenhuma data real no histórico não são tocados e são listados.

Uso:
    cd backend
    py fix_fallback_2014.py           # só mostra o que faria
    py fix_fallback_2014.py --apply   # aplica
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sqlalchemy import text
from app.core.database import SessionLocal

FALLBACK = "2014-01-01"

PLAN_SQL = f"""
WITH bad AS (
    SELECT id, number, status FROM orders WHERE created_at::date = '{FALLBACK}'
),
d AS (
    SELECT b.*,
        (SELECT max(changed_at) FROM order_status_history h
          WHERE h.order_id = b.id AND h.status = 'DELIVERED'
            AND h.changed_at::date <> '{FALLBACK}') AS delivered,
        (SELECT min(changed_at) FROM order_status_history h
          WHERE h.order_id = b.id AND h.changed_at::date <> '{FALLBACK}') AS first_real,
        (SELECT max(changed_at) FROM order_status_history h
          WHERE h.order_id = b.id AND h.changed_at::date <> '{FALLBACK}') AS last_real
    FROM bad b
)
SELECT id, number, status,
       first_real AS new_created_at,
       CASE WHEN delivered IS NOT NULL THEN delivered
            WHEN status = 'PAID' THEN last_real
       END AS new_paid_at
FROM d
ORDER BY number
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Aplica as alterações")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plan = db.execute(text(PLAN_SQL)).fetchall()
        fixable = [r for r in plan if r.new_created_at is not None]
        manual = [r for r in plan if r.new_created_at is None or r.new_paid_at is None]

        print(f"[INFO] {len(plan)} pedido(s) com data {FALLBACK}")
        print(f"[INFO] {len(fixable)} com datas reais no histórico para corrigir")
        for r in fixable[:10]:
            paid = r.new_paid_at.date() if r.new_paid_at else "(mantém)"
            print(f"    #{r.number}: pedido -> {r.new_created_at.date()}, pago -> {paid}")
        if len(fixable) > 10:
            print(f"    ... e mais {len(fixable) - 10}")

        if manual:
            print("\n[REVISAR À MÃO] Pagamento continua em 2014-01-01:")
            for r in manual:
                print(f"    #{r.number} ({r.status})")

        if not args.apply:
            print("\n[DRY-RUN] Nenhuma alteração feita. Use --apply para aplicar.")
            return

        for r in fixable:
            if r.new_paid_at is not None:
                db.execute(text(f"""
                    UPDATE order_status_history SET changed_at = :dt
                    WHERE order_id = :oid AND status = 'PAID' AND changed_at::date = '{FALLBACK}'
                """), {"dt": r.new_paid_at, "oid": r.id})
            db.execute(text(f"""
                UPDATE order_status_history SET changed_at = :dt
                WHERE order_id = :oid AND status <> 'PAID' AND changed_at::date = '{FALLBACK}'
            """), {"dt": r.new_created_at, "oid": r.id})
            db.execute(text("UPDATE orders SET created_at = :dt WHERE id = :oid"),
                       {"dt": r.new_created_at, "oid": r.id})

        db.commit()
        print(f"\n[OK] {len(fixable)} pedido(s) corrigido(s).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
