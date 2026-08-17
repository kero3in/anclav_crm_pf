import os
import time
import requests
import psycopg2
import logging
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = os.getenv("AQSI_TOKEN")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("POSTGRES_DB", "anclav_crm")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

URL = "https://api.aqsi.ru/pub/v4/Receipts"
HEADERS = {
    "x-client-key": f"Application {API_KEY}",
    "Content-Type": "application/json"
}

def get_db_connection():
    return psycopg2.connect(host=DB_HOST, port="5432", database=DB_NAME, user=DB_USER, password=DB_PASS)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id VARCHAR(100) PRIMARY KEY,
            transaction_time TIMESTAMP NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            terminal_id VARCHAR(50),
            cashier_name VARCHAR(255),
            client_id VARCHAR(100)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS receipt_items (
            id SERIAL PRIMARY KEY,
            receipt_id VARCHAR(100) REFERENCES receipts(receipt_id) ON DELETE CASCADE,
            item_name VARCHAR(255) NOT NULL,
            quantity NUMERIC(10, 2) NOT NULL,
            price NUMERIC(10, 2) NOT NULL,
            total NUMERIC(10, 2) NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def get_last_sync_date():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(transaction_time) FROM receipts")
    result = cur.fetchone()[0]
    cur.close()
    conn.close()

    if result:
        return (result + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")
    return (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")

def fetch_and_save_data():
    if not API_KEY:
        logging.error("AQSI_TOKEN is not set. Synchronization aborted.")
        return

    begin_date = get_last_sync_date()
    end_date = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")

    page = 1
    page_size = 100
    conn = get_db_connection()
    cur = conn.cursor()

    logging.info(f"Starting synchronization from {begin_date} to {end_date}")

    while True:
        params = {
            "filtered.processedAtTzFrom": begin_date,
            "filtered.processedAtTzTo": end_date,
            "pageSize": page_size,
            "page": page
        }

        response = requests.get(URL, headers=HEADERS, params=params)

        if response.status_code != 200:
            logging.error(f"API Error: {response.status_code} - {response.text}")
            break

        rows = response.json().get("rows", [])
        if not rows:
            break

        receipts_data = []
        items_data = []

        for row in rows:
            receipt_id = row.get("id")
            info = row.get("info") or {}

            raw_time = info.get("dateTime") or row.get("createdAt")
            trans_time = raw_time.split('.')[0].replace('Z', '') if raw_time else None

            amount = float(info.get("sum", 0)) / 100
            terminal_id = str(info.get("deviceSerialNumber", "Unknown"))

            cashier_info = info.get("cashierInfo") or {}
            cashier_name = cashier_info.get("positionAndSurname", "Unknown") if isinstance(cashier_info, dict) else "Unknown"

            customer_info = info.get("customerInfo") or {}
            client_id = customer_info.get("externalId")

            receipts_data.append((receipt_id, trans_time, amount, terminal_id, cashier_name, client_id))

            positions = row.get("positions", [])
            for pos in positions:
                pos_info = pos.get("info") or {}
                item_name = pos_info.get("name", "Unknown item").strip()
                qty = float(pos_info.get("quantity", 0))
                price = float(pos_info.get("finalPrice", 0)) / 100
                total = qty * price

                items_data.append((receipt_id, item_name, qty, price, total))

        if receipts_data:
            batch_receipt_ids = [r[0] for r in receipts_data]

            cur.execute('DELETE FROM receipt_items WHERE receipt_id = ANY(%s)', (batch_receipt_ids,))

            inserted_records = execute_values(cur, '''
                INSERT INTO receipts (receipt_id, transaction_time, amount, terminal_id, cashier_name, client_id)
                VALUES %s
                ON CONFLICT (receipt_id) DO NOTHING
                RETURNING receipt_id, client_id
            ''', receipts_data, fetch=True)

            execute_values(cur, '''
                INSERT INTO receipt_items (receipt_id, item_name, quantity, price, total)
                VALUES %s
            ''', items_data)

            if inserted_records:
                today_str = datetime.now().strftime("%d.%m.%Y")

                for rec_id, c_id in inserted_records:
                    if not c_id:
                        continue

                    cur.execute('''
                        UPDATE users
                        SET visits_count = COALESCE(visits_count, 0) + 1,
                            last_visit = %s
                        WHERE aqsi_client_id = %s
                        RETURNING tg_id, visits_count
                    ''', (today_str, c_id))

                    user_data = cur.fetchone()

                    if user_data:
                        tg_id, new_visits = user_data

                        cur.execute('''
                            INSERT INTO feedback_queue (tg_id, receipt_id, scheduled_time, task_type)
                            VALUES (%s, %s, NOW(), 'visit')
                        ''', (tg_id, rec_id))

                        if new_visits == 1 or new_visits % 5 == 0:
                            scheduled_time = datetime.now() + timedelta(minutes=15)
                            cur.execute('''
                                INSERT INTO feedback_queue (tg_id, receipt_id, scheduled_time, task_type)
                                VALUES (%s, %s, %s, 'feedback')
                            ''', (tg_id, rec_id, scheduled_time))
                            logging.info(f"Scheduled feedback request for tg_id: {tg_id}, visit count: {new_visits}")

            conn.commit()
            logging.info(f"Successfully saved {len(receipts_data)} receipts (Page {page})")

        page += 1

    cur.close()
    conn.close()
    logging.info("Synchronization completed.")

if __name__ == "__main__":
    logging.info("AQSI Sync worker started.")
    init_db()

    while True:
        try:
            fetch_and_save_data()
        except Exception as e:
            logging.error(f"Critical error during synchronization: {e}")

        time.sleep(300)
