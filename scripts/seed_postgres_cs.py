# scripts/seed_postgres_cs.py
import os
import json
import pathlib
import psycopg

# ---------- Config ----------
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "cs_support")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

OUT_TESTS_DIR = pathlib.Path("tests")
OUT_TESTS_DIR.mkdir(parents=True, exist_ok=True)
OUT_TESTS_FILE = OUT_TESTS_DIR / "tool_test_cases.json"

CONN_INFO = f"host={PGHOST} port={PGPORT} dbname={PGDATABASE} user={PGUSER} password={PGPASSWORD}"

# ---------- DDL ----------
DDL = """
BEGIN;

-- Drop in dependency order (idempotent seed)
DROP TABLE IF EXISTS shipment_events CASCADE;
DROP TABLE IF EXISTS returns CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS shipping_methods CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
  customer_id    INT PRIMARY KEY,
  name           VARCHAR(100) NOT NULL,
  email          VARCHAR(120) NOT NULL,
  country        VARCHAR(2)   NOT NULL,
  city           VARCHAR(80)  NOT NULL
);

CREATE TABLE shipping_methods (
  shipping_method_id SERIAL PRIMARY KEY,
  name           VARCHAR(60) NOT NULL,
  region         VARCHAR(32) NOT NULL,        -- e.g. 'US', 'CA', 'World'
  carrier        VARCHAR(40) NOT NULL,        -- e.g. UPS/DHL
  cost           NUMERIC(10,2) NOT NULL,
  est_days_min   INT NOT NULL,
  est_days_max   INT NOT NULL,
  description    TEXT
);

CREATE TABLE products (
  product_id INT PRIMARY KEY,
  sku        VARCHAR(40) UNIQUE,
  title      VARCHAR(160) NOT NULL
);

CREATE TABLE orders (
  order_id          INT PRIMARY KEY,
  customer_id       INT NOT NULL REFERENCES customers(customer_id),
  order_date        TIMESTAMP NOT NULL,
  status            VARCHAR(32) NOT NULL,  -- e.g. PendingPayment, Shipped, Delivered, Canceled
  status_updated_at TIMESTAMP NOT NULL,
  shipped_date      TIMESTAMP NULL,
  eta_date          DATE NULL,
  tracking_no       VARCHAR(40),
  carrier           VARCHAR(40),
  shipping_method_id INT REFERENCES shipping_methods(shipping_method_id),
  destination_country VARCHAR(2) NOT NULL,
  destination_city    VARCHAR(80) NOT NULL,
  total_amount      NUMERIC(10,2) NOT NULL,
  currency          VARCHAR(3) NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_tracking ON orders(tracking_no) WHERE tracking_no IS NOT NULL;

CREATE TABLE order_items (
  order_id   INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  product_id INT NOT NULL REFERENCES products(product_id),
  qty        INT NOT NULL CHECK (qty > 0),
  price      NUMERIC(10,2) NOT NULL,
  PRIMARY KEY(order_id, product_id)
);

CREATE TABLE payments (
  payment_id   SERIAL PRIMARY KEY,
  order_id     INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  method       VARCHAR(32) NOT NULL,      -- CreditCard, PayPal, etc
  amount       NUMERIC(10,2) NOT NULL,
  currency     VARCHAR(3) NOT NULL,
  status       VARCHAR(20) NOT NULL,      -- Completed, Failed, Pending, Refunded
  last_attempt TIMESTAMP NOT NULL,
  failure_code   VARCHAR(64),
  failure_reason TEXT
);

CREATE TABLE returns (
  return_id    SERIAL PRIMARY KEY,
  order_id     INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  product_id   INT REFERENCES products(product_id),
  request_date DATE NOT NULL,
  status       VARCHAR(20) NOT NULL,      -- Pending, Approved, Rejected, Completed
  approved     BOOLEAN DEFAULT FALSE,
  refund_amount NUMERIC(10,2),
  currency      VARCHAR(3),
  notes        TEXT
);

CREATE TABLE shipment_events (
  event_id    SERIAL PRIMARY KEY,
  tracking_no VARCHAR(40) NOT NULL,
  event_time  TIMESTAMP NOT NULL,
  status      VARCHAR(60) NOT NULL,  -- In Transit, Out for Delivery, Delivered, Shipment on Hold, etc.
  location    VARCHAR(120),
  details     TEXT
);

COMMIT;
"""

# ---------- Seed Data ----------
def seed_data(cur):
    # customers
    cur.execute("""
    INSERT INTO customers (customer_id, name, email, country, city) VALUES
    (501, 'Alice Johnson', 'alice@example.com', 'US', 'New York'),
    (502, 'Bob Smith',     'bob@example.com',   'US', 'San Francisco'),
    (503, 'Carlos Diaz',   'carlos@example.com','ES', 'Madrid'),
    (504, 'Diana Lee',     'diana@example.com', 'CA', 'Toronto'),
    (505, 'Eva Nowak',     'eva@example.com',   'PL', 'Warsaw');
    """)

    # shipping methods
    cur.execute("""
    INSERT INTO shipping_methods (name, region, carrier, cost, est_days_min, est_days_max, description) VALUES
    ('Standard',      'US',    'UPS',  5.00, 3, 5, 'Ground shipping in the US'),
    ('Express',       'US',    'UPS', 15.00, 1, 2, 'Expedited shipping in the US'),
    ('International', 'World', 'DHL', 25.00, 7, 12, 'International shipping (most countries)');
    """)

    # products
    cur.execute("""
    INSERT INTO products (product_id, sku, title) VALUES
    (101, 'NC-HEADPHONES', 'Noise-Cancelling Headphones'),
    (102, 'USB-C-65W',     'USB-C Charger 65W'),
    (103, 'RUN-SHOES',     'Running Shoes');
    """)

    # orders
    cur.execute("""
    INSERT INTO orders
    (order_id, customer_id, order_date, status, status_updated_at, shipped_date, eta_date, tracking_no, carrier, shipping_method_id, destination_country, destination_city, total_amount, currency)
    VALUES
    (1001, 501, '2025-07-30 10:00', 'Shipped',   '2025-08-01 14:30', '2025-08-01 14:30', '2025-08-05', 'TRK1001', 'UPS',  1, 'US', 'New York',      59.99, 'USD'),
    (1002, 502, '2025-07-31 12:15', 'PendingPayment', '2025-08-01 14:00', NULL, NULL, NULL, NULL, 2, 'US', 'San Francisco', 120.00, 'USD'),
    (1003, 503, '2025-07-18 09:20', 'Delivered','2025-07-20 18:45', '2025-07-19 08:10', '2025-07-20', 'TRK1003', 'DHL',  3, 'ES', 'Madrid',       89.00, 'EUR'),
    (1004, 504, '2025-07-29 16:40', 'Shipped',   '2025-08-02 10:00', '2025-08-02 09:00', '2025-08-08', 'TRK1004', 'DHL',  3, 'CA', 'Toronto',     149.00, 'CAD'),
    (1005, 505, '2025-08-01 11:05', 'Canceled',  '2025-08-01 12:00', NULL, NULL, NULL, NULL, 1, 'PL', 'Warsaw',  45.50, 'PLN');
    """)

    # order items
    cur.execute("""
    INSERT INTO order_items (order_id, product_id, qty, price) VALUES
    (1001, 101, 1, 59.99),
    (1002, 102, 2, 60.00),
    (1003, 103, 1, 89.00),
    (1004, 101, 1, 149.00),
    (1005, 102, 1, 45.50);
    """)

    # payments
    cur.execute("""
    INSERT INTO payments (order_id, method, amount, currency, status, last_attempt, failure_code, failure_reason) VALUES
    (1001, 'CreditCard', 59.99, 'USD', 'Completed', '2025-07-30 10:01', NULL, NULL),
    (1002, 'CreditCard',120.00, 'USD', 'Failed',    '2025-08-01 14:00', 'card_declined', 'Issuer declined the transaction'),
    (1003, 'PayPal',     89.00, 'EUR', 'Completed', '2025-07-18 09:22', NULL, NULL),
    (1004, 'CreditCard',149.00, 'CAD', 'Completed', '2025-07-29 16:41', NULL, NULL),
    (1005, 'CreditCard', 45.50, 'PLN', 'Refunded',  '2025-08-01 12:00', NULL, 'Order canceled and refunded');
    """)

    # returns
    cur.execute("""
    INSERT INTO returns (order_id, product_id, request_date, status, approved, refund_amount, currency, notes) VALUES
    (1003, 103, '2025-08-05', 'Pending', FALSE, NULL, NULL, 'Customer requested size exchange');
    """)

    # shipment events
    cur.execute("""
    INSERT INTO shipment_events (tracking_no, event_time, status, location, details) VALUES
    ('TRK1001', '2025-08-01 15:00', 'Shipment picked up', 'New York, NY', 'Label created, package picked up'),
    ('TRK1001', '2025-08-02 08:10', 'In Transit',         'Harrisburg, PA', 'Departed facility'),
    ('TRK1001', '2025-08-03 07:30', 'In Transit',         'Newark, NJ',     'Arrived at facility'),

    ('TRK1003', '2025-07-19 07:50', 'Out for Delivery',   'Madrid, ES',     'Courier en route'),
    ('TRK1003', '2025-07-20 18:45', 'Delivered',          'Madrid, ES',     'Left at front door'),

    ('TRK1004', '2025-08-02 09:00', 'In Transit',         'Montreal, QC',   'Arrived at facility'),
    ('TRK1004', '2025-08-03 10:00', 'Shipment on Hold',   'Toronto, ON',    'Clearance delay - awaiting documentation');
    """)

# ---------- Test Cases (gold answers) ----------
def build_test_cases():
    # Набор коротких эталонов — удобно для assert "contains"
    return [
        # TRACKING_STATUS
        {
            "id": "TS_1",
            "intent": "TRACKING_STATUS",
            "question": "Где сейчас мой заказ 1001?",
            "expected_answer": "Заказ 1001: статус Shipped (в пути). Последнее событие: In Transit (Newark, NJ, 2025-08-03 07:30). Трек-номер TRK1001, перевозчик UPS. Ожидаемая доставка: 2025-08-05."
        },
        {
            "id": "TS_2",
            "intent": "TRACKING_STATUS",
            "question": "Статус заказа #1004?",
            "expected_answer": "Заказ 1004: статус Shipped. Последнее событие трекинга: Shipment on Hold (Toronto, ON, 2025-08-03 10:00) — задержка на таможне/оформлении. Трек-номер TRK1004, перевозчик DHL. ETA: 2025-08-08."
        },
        {
            "id": "TS_3",
            "intent": "TRACKING_STATUS",
            "question": "Доставлен ли заказ 1003?",
            "expected_answer": "Заказ 1003: статус Delivered (2025-07-20 18:45, Madrid, ES). Трек-номер TRK1003, перевозчик DHL."
        },

        # DELIVERY_OPTIONS
        {
            "id": "DO_1",
            "intent": "DELIVERY_OPTIONS",
            "question": "Какие есть варианты доставки по США?",
            "expected_answer": "Варианты по США: Standard (UPS, 3–5 дн., $5.00) и Express (UPS, 1–2 дн., $15.00)."
        },
        {
            "id": "DO_2",
            "intent": "DELIVERY_OPTIONS",
            "question": "Сколько стоит международная доставка в Испанию?",
            "expected_answer": "Международная доставка: International (DHL, 7–12 дн., $25.00)."
        },
        {
            "id": "DO_3",
            "intent": "DELIVERY_OPTIONS",
            "question": "Сроки и перевозчик для международной доставки?",
            "expected_answer": "International: DHL, ориентировочно 7–12 дней."
        },

        # PAYMENT_RETRY
        {
            "id": "PR_1",
            "intent": "PAYMENT_RETRY",
            "question": "Оплата по заказу 1002 не прошла. Что делать?",
            "expected_answer": "По заказу 1002 последняя попытка оплаты: Failed (2025-08-01 14:00), причина: card_declined — Issuer declined the transaction. Предлагаю повторить оплату другой картой/методом или проверить лимиты и реквизиты."
        },
        {
            "id": "PR_2",
            "intent": "PAYMENT_RETRY",
            "question": "Могу ли я повторить оплату заказа 1002?",
            "expected_answer": "Да, возможен повторный платеж. Текущий статус оплаты — Failed; попробуйте другой способ оплаты или снова картой после проверки у банка."
        },
        {
            "id": "PR_3",
            "intent": "PAYMENT_RETRY",
            "question": "Почему списание не прошло по заказу #1002?",
            "expected_answer": "Причина отклонения: card_declined (Issuer declined the transaction). Рекомендуем связаться с банком или использовать альтернативный метод."
        },

        # RETURN_ISSUE
        {
            "id": "RI_1",
            "intent": "RETURN_ISSUE",
            "question": "Хочу вернуть товар из заказа 1003",
            "expected_answer": "По заказу 1003 уже есть запрос на возврат: статус Pending (от 2025-08-05), позиция: Running Shoes. Ожидает обработки."
        },
        {
            "id": "RI_2",
            "intent": "RETURN_ISSUE",
            "question": "Каков статус моего возврата по заказу 1003?",
            "expected_answer": "Запрос на возврат по 1003: статус Pending (ожидает одобрения). Как только вернём — получите подтверждение и информацию по возврату средств."
        },
        {
            "id": "RI_3",
            "intent": "RETURN_ISSUE",
            "question": "Можно ли сделать обмен по заказу 1003?",
            "expected_answer": "По 1003 оформлен возврат (Pending). После одобрения возможен обмен/повторный заказ — уточним детали модели/размера."
        }
    ]

# ---------- Main ----------
def main():
    print(f"Connecting to {PGUSER}@{PGHOST}:{PGPORT}/{PGDATABASE} ...")
    with psycopg.connect(CONN_INFO, autocommit=True) as conn:
        with conn.cursor() as cur:
            print("Applying DDL ...")
            cur.execute(DDL)
            print("Seeding data ...")
            seed_data(cur)

    # write test cases
    cases = build_test_cases()
    OUT_TESTS_FILE.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✔ Test cases written to {OUT_TESTS_FILE}")

    print("✅ Done. Database ready for tool tests.")

if __name__ == "__main__":
    main()