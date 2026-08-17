import os
import psycopg2
import hmac
import hashlib
import json
import logging
from urllib.parse import unquote, parse_qsl
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from datetime import datetime, date
from contextlib import asynccontextmanager

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
MASTER_TOKEN = os.getenv("MASTER_TOKEN")

# OPEX limits logic
OPEX_MONTHLY = {
    '1010625022006769': 182548.0,
    '1010977707053285': 147459.0
}

def get_daily_opex(target_date, terminal_id=None):
    daily_opex = 0
    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    if terminal_id in OPEX_MONTHLY:
        if terminal_id == '1010977707053285' and target_date < date(2026, 7, 1):
            return 0
        return OPEX_MONTHLY[terminal_id] / 30

    daily_opex += OPEX_MONTHLY['1010625022006769'] / 30
    if target_date >= date(2026, 7, 1):
        daily_opex += OPEX_MONTHLY['1010977707053285'] / 30

    return daily_opex

def validate_tma(init_data: str) -> bool:
    try:
        parsed = dict(parse_qsl(init_data))
        if "hash" not in parsed:
            return False
        received_hash = parsed.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return calc_hash == received_hash
    except Exception:
        return False

def verify_access(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token format")

    scheme, token = parts

    if scheme == "Bearer":
        if token != MASTER_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid master token")
        return True
    elif scheme == "tma":
        if not validate_tma(token):
            raise HTTPException(status_code=401, detail="Invalid signature")
        return True
    else:
        raise HTTPException(status_code=401, detail="Unknown authorization scheme")

def init_db_api():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS active_terminal_id VARCHAR(50);")

        cur.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                prices JSONB NOT NULL,
                category VARCHAR(100),
                allowed_modifiers JSONB,
                is_available BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT REFERENCES users(tg_id),
                terminal_id VARCHAR(50),
                status VARCHAR(50) DEFAULT 'new',
                total_amount NUMERIC(10, 2),
                is_notified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
                quantity INTEGER DEFAULT 1,
                modifiers JSONB
            );
        ''')
        conn.commit()
        logging.info("API database tables initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing API database tables: {e}")
    finally:
        cur.close()
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_api()
    yield

app = FastAPI(title="ANCLAV CRM API", dependencies=[Depends(verify_access)], lifespan=lifespan)

cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allow_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "anclav_crm"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres")
    )

def categorize_item(name):
    name_lower = str(name).lower()
    promos = ['вкус анклава', 'гармония анклава', 'энергия анклава']
    merch = ['зерно', 'дрип', 'сертификат', 'labukelly', 'коробка']
    food = ['печенье', 'донат', 'панини', 'круассан', 'макарон', 'киш', 'сэндвич', 'торт', 'десерт', 'моти', 'сырок', 'батончик', 'чизкейк', 'tart', 'тарт', 'сырник', 'эклер', 'трубочка', 'брауни', 'картошка', 'орешки', 'булочка', 'блин', 'улитка', 'слойка', 'маффин', 'корзиночка', 'ozera']
    addons = ['сироп', 'молоко', 'сливки', 'мед', 'мёд', 'доп.', 'маршмеллоу', 'сыр ', 'база']
    drinks = ['капучино', 'раф', 'латте', 'американо', 'эспрессо', 'матча', 'чай', 'фильтр', 'флет', 'флэт', 'какао', 'мокачино', 'айс', 'бамбл', 'тоник', 'кофе', 'глинтвейн', 'лимонад', 'мл', 'тучки', 'груша', 'настроение']

    if any(promo in name_lower for promo in promos): return 'Акции'
    if any(word in name_lower for word in merch): return 'Мерч/Зерно'
    if any(word in name_lower for word in food): return 'Еда'
    if any(word in name_lower for word in addons): return 'Добавки'
    if any(word in name_lower for word in drinks): return 'Напитки'
    return 'Остальное'

def get_where_clause(start_date, end_date, terminal_id=None, prefix=""):
    conditions = []
    params = []
    if start_date:
        conditions.append(f"{prefix}transaction_time >= %s::timestamp")
        params.append(start_date)
    if end_date:
        conditions.append(f"{prefix}transaction_time <= %s::timestamp")
        params.append(f"{end_date} 23:59:59")
    if terminal_id:
        conditions.append(f"{prefix}terminal_id = %s")
        params.append(terminal_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    return where_clause, params

@app.get("/api/dashboard/date_limits")
def get_date_limits():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT MIN(DATE(transaction_time)) as min_date, MAX(DATE(transaction_time)) as max_date FROM receipts")
        data = cur.fetchone()
        return {
            "min_date": str(data["min_date"]) if data["min_date"] else None,
            "max_date": str(data["max_date"]) if data["max_date"] else None
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/summary")
def get_summary(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id, "r.")
        cur.execute(f"""
            WITH calc AS (
                SELECT r.receipt_id, r.amount,
                       COALESCE(SUM(ri.quantity), 0) as items_qty,
                       COALESCE(SUM(ri.total_cost) * 0.971153, 0) as receipt_cost,
                       DATE(r.transaction_time) as receipt_date
                FROM receipts r
                LEFT JOIN receipt_items ri ON r.receipt_id = ri.receipt_id
                {where_sql}
                GROUP BY r.receipt_id, r.amount, DATE(r.transaction_time)
            )
            SELECT COUNT(receipt_id) as total_receipts,
                   COALESCE(SUM(amount), 0) as total_revenue,
                   COALESCE(SUM(receipt_cost), 0) as total_cogs,
                   COALESCE(SUM(items_qty) / NULLIF(COUNT(receipt_id), 0), 0) as upt,
                   ARRAY_AGG(DISTINCT receipt_date) as active_dates
            FROM calc
        """, tuple(params))
        data = cur.fetchone()

        revenue = float(data["total_revenue"]) if data else 0
        cogs = float(data["total_cogs"]) if data else 0

        total_opex = 0
        if data and data["active_dates"]:
            for d in data["active_dates"]:
                total_opex += get_daily_opex(d, terminal_id)

        profit = revenue - cogs - total_opex
        margin = (profit / revenue * 100) if revenue > 0 else 0

        return {
            "total_receipts": int(data["total_receipts"]) if data else 0,
            "total_revenue": revenue,
            "total_profit": profit,
            "margin_percent": round(margin, 1),
            "upt": round(float(data["upt"]), 1) if data else 0
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/daily_revenue")
def get_daily_revenue(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id, "r.")
        cur.execute(f"""
            SELECT DATE(r.transaction_time) as date,
                   SUM(ri.total) as revenue,
                   COALESCE(SUM(ri.total_cost) * 0.971153, 0) as adjusted_cogs
            FROM receipts r
            LEFT JOIN receipt_items ri ON r.receipt_id = ri.receipt_id
            {where_sql}
            GROUP BY DATE(r.transaction_time)
            ORDER BY date ASC
        """, tuple(params))

        rows = cur.fetchall()
        result = []

        for row in rows:
            current_date = row["date"]
            revenue = float(row["revenue"])
            cogs = float(row["adjusted_cogs"])

            daily_opex = get_daily_opex(current_date, terminal_id)
            profit = revenue - cogs - daily_opex

            result.append({
                "date": str(current_date),
                "revenue": revenue,
                "profit": profit
            })

        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/hourly")
def get_hourly_stats(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id)
        cur.execute(f"""
            SELECT EXTRACT(HOUR FROM transaction_time)::int as hour, COUNT(receipt_id) as receipts_count, COALESCE(SUM(amount), 0) as revenue
            FROM receipts {where_sql} GROUP BY hour ORDER BY hour ASC
        """, tuple(params))
        rows = cur.fetchall()
        return [{"hour": f"{row['hour']}:00", "revenue": float(row["revenue"]), "receipts_count": int(row["receipts_count"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/crm_stats")
def get_crm_stats(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id)
        cur.execute(f"""
            SELECT CASE WHEN client_id IS NOT NULL THEN 'Loyalty' ELSE 'Anonymous' END as client_type,
                   COUNT(receipt_id) as receipts_count, COALESCE(SUM(amount), 0) as total_revenue
            FROM receipts {where_sql} GROUP BY client_type
        """, tuple(params))
        rows = cur.fetchall()
        return [{"type": str(row["client_type"]), "receipts_count": int(row["receipts_count"]), "total_revenue": float(row["total_revenue"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/points")
def get_points_stats(start_date: str = None, end_date: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date)
        cur.execute(f"""
            SELECT terminal_id, COUNT(receipt_id) as receipts_count, COALESCE(SUM(amount), 0) as total_revenue
            FROM receipts {where_sql} GROUP BY terminal_id ORDER BY total_revenue DESC
        """, tuple(params))
        rows = cur.fetchall()
        return [{"terminal_id": str(row["terminal_id"]), "receipts_count": int(row["receipts_count"]), "total_revenue": float(row["total_revenue"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/barista")
def get_barista_stats(start_date: str = None, end_date: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date)
        cur.execute(f"""
            SELECT
                cashier_name,
                terminal_id,
                COUNT(receipt_id) as receipts_count,
                COALESCE(SUM(amount), 0) as total_revenue,
                COUNT(DISTINCT DATE(transaction_time)) as shifts_count
            FROM receipts {where_sql}
            GROUP BY cashier_name, terminal_id
            ORDER BY total_revenue DESC
        """, tuple(params))
        rows = cur.fetchall()
        return [{"cashier_name": str(row["cashier_name"]), "terminal_id": str(row["terminal_id"]), "receipts_count": int(row["receipts_count"]), "total_revenue": float(row["total_revenue"]), "shifts_count": int(row["shifts_count"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/categories")
def get_categories_stats(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id, "r.")
        cur.execute(f"""
            SELECT ri.item_name, SUM(ri.total) as revenue
            FROM receipt_items ri JOIN receipts r ON ri.receipt_id = r.receipt_id
            {where_sql} GROUP BY ri.item_name
        """, tuple(params))
        rows = cur.fetchall()
        cats = {'Акции': 0, 'Мерч/Зерно': 0, 'Еда': 0, 'Добавки': 0, 'Напитки': 0, 'Остальное': 0}
        for r in rows:
            category = categorize_item(r['item_name'])
            cats[category] += float(r['revenue'])
        return [{"category": k, "revenue": v} for k, v in cats.items() if v > 0]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/abc")
def get_abc_analysis(start_date: str = None, end_date: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, None, "r.")
        cur.execute(f"""
            SELECT ri.item_name, SUM(ri.total) as revenue
            FROM receipt_items ri JOIN receipts r ON ri.receipt_id = r.receipt_id
            {where_sql} GROUP BY ri.item_name ORDER BY revenue DESC
        """, tuple(params))
        rows = cur.fetchall()
        total_revenue = sum(float(r['revenue']) for r in rows)
        if total_revenue == 0: return []
        abc_data = []
        cum_sum = 0
        for r in rows[:50]:
            rev = float(r['revenue'])
            cum_sum += rev
            abc_data.append({"item": str(r['item_name']), "revenue": rev, "cum_percent": round((cum_sum / total_revenue) * 100, 1)})
        return abc_data
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/basket")
def get_basket_analysis(start_date: str = None, end_date: str = None, terminal_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id, "r.")
        cur.execute(f"""
            SELECT a.item_name AS item_a, b.item_name AS item_b, COUNT(DISTINCT r.receipt_id) as frequency
            FROM receipt_items a
            JOIN receipt_items b ON a.receipt_id = b.receipt_id AND a.item_name < b.item_name
            JOIN receipts r ON a.receipt_id = r.receipt_id
            {where_sql}
            GROUP BY item_a, item_b
            ORDER BY frequency DESC
            LIMIT 15
        """, tuple(params))
        rows = cur.fetchall()
        return [{"item_a": str(row["item_a"]), "item_b": str(row["item_b"]), "frequency": int(row["frequency"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/rfm_cohorts")
def get_crm_analytics(start_date: str = None, end_date: str = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date)
        cur.execute(f"""
            SELECT client_id, MAX(transaction_time) as last_visit, COUNT(receipt_id) as frequency, SUM(amount) as monetary
            FROM receipts WHERE client_id IS NOT NULL {('AND ' + where_sql.replace('WHERE ', '')) if where_sql else ''}
            GROUP BY client_id
        """, tuple(params))
        users = cur.fetchall()

        segments = {"Champions": 0, "Loyal": 0, "At Risk": 0, "New": 0, "Lost": 0}
        now = datetime.now()
        for u in users:
            days_since = (now - u['last_visit']).days
            f = u['frequency']
            if days_since <= 14 and f >= 5: segments["Champions"] += 1
            elif days_since <= 30 and f >= 2: segments["Loyal"] += 1
            elif days_since > 30 and f >= 2: segments["At Risk"] += 1
            elif f == 1 and days_since <= 14: segments["New"] += 1
            else: segments["Lost"] += 1

        cur.execute(f"""
            WITH first_visit AS (SELECT client_id, DATE_TRUNC('month', MIN(transaction_time)) as cohort_month FROM receipts WHERE client_id IS NOT NULL GROUP BY client_id),
            activity AS (SELECT r.client_id, DATE_TRUNC('month', r.transaction_time) as activity_month FROM receipts r WHERE client_id IS NOT NULL)
            SELECT TO_CHAR(f.cohort_month, 'YYYY-MM') as cohort, TO_CHAR(a.activity_month, 'YYYY-MM') as activity, COUNT(DISTINCT a.client_id) as users_count
            FROM first_visit f JOIN activity a ON f.client_id = a.client_id
            GROUP BY f.cohort_month, a.activity_month ORDER BY f.cohort_month, a.activity_month
        """)
        cohorts = cur.fetchall()

        return {"has_data": len(users) > 0, "rfm": [{"segment": k, "count": v} for k, v in segments.items() if v > 0], "cohorts": [{"cohort": str(c["cohort"]), "activity": str(c["activity"]), "users": int(c["users_count"])} for c in cohorts]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/dashboard/cross_sell")
def get_cross_sell_analysis(item_name: str, start_date: str = None, end_date: str = None, terminal_id: str = None):
    if not item_name:
        return []

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        where_sql, params = get_where_clause(start_date, end_date, terminal_id, "r.")
        join_condition = "AND" if where_sql else "WHERE"
        query = f"""
            SELECT b.item_name, COUNT(DISTINCT r.receipt_id) as frequency
            FROM receipt_items a
            JOIN receipt_items b ON a.receipt_id = b.receipt_id AND a.item_name != b.item_name
            JOIN receipts r ON a.receipt_id = r.receipt_id
            {where_sql} {join_condition} a.item_name ILIKE %s
            GROUP BY b.item_name
            ORDER BY frequency DESC
            LIMIT 5
        """
        params.append(f"%{item_name}%")

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [{"item": str(row["item_name"]), "frequency": int(row["frequency"])} for row in rows]
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

def get_tg_id_from_tma(token: str):
    try:
        parsed = dict(parse_qsl(token))
        user_data = json.loads(unquote(parsed.get('user', '{}')))
        return user_data.get('id')
    except Exception:
        return None

@app.get("/api/menu")
def get_menu():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM menu_items WHERE is_available = TRUE ORDER BY category, id")
        items = cur.fetchall()

        menu_grouped = {}
        for item in items:
            cat = item['category'] or 'Остальное'
            if cat not in menu_grouped:
                menu_grouped[cat] = []
            menu_grouped[cat].append(item)

        return {"status": "success", "menu": menu_grouped}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.post("/api/orders")
def create_order(payload: dict, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=403, detail="Access denied")

    tg_id = get_tg_id_from_tma(authorization.split(" ")[1])
    if not tg_id:
        raise HTTPException(status_code=400, detail="Invalid user identification")

    terminal_id = payload.get("terminal_id")
    items = payload.get("items", [])
    total_amount = payload.get("total_amount", 0)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO orders (tg_id, terminal_id, total_amount, is_notified)
            VALUES (%s, %s, %s, FALSE) RETURNING id
        """, (tg_id, terminal_id, total_amount))
        order_id = cur.fetchone()[0]

        for item in items:
            cur.execute("""
                INSERT INTO order_items (order_id, menu_item_id, quantity, modifiers)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['menu_item_id'], item.get('quantity', 1), json.dumps(item.get('modifiers', {}))))

        conn.commit()
        return {"status": "success", "order_id": order_id}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/orders/last")
def get_last_order(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("tma "):
        return {"status": "success", "last_order": None}

    tg_id = get_tg_id_from_tma(authorization.split(" ")[1])

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, terminal_id FROM orders WHERE tg_id = %s ORDER BY created_at DESC LIMIT 1", (tg_id,))
        last_order = cur.fetchone()

        if not last_order:
            return {"status": "success", "last_order": None}

        cur.execute("SELECT menu_item_id, quantity, modifiers FROM order_items WHERE order_id = %s", (last_order['id'],))
        items = cur.fetchall()

        return {
            "status": "success",
            "last_order": {
                "terminal_id": last_order['terminal_id'],
                "items": items
            }
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.post("/api/admin/menu")
def add_menu_item(payload: dict, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO menu_items (name, description, prices, category, allowed_modifiers, is_available)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            payload['name'],
            payload.get('description', ''),
            json.dumps(payload['prices']),
            payload.get('category', 'Остальное'),
            json.dumps(payload.get('allowed_modifiers', [])),
            payload.get('is_available', True)
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        return {"status": "success", "item_id": new_id}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.put("/api/admin/menu/{item_id}")
def update_menu_item(item_id: int, payload: dict, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        update_fields = []
        values = []

        if 'name' in payload:
            update_fields.append("name = %s")
            values.append(payload['name'])
        if 'description' in payload:
            update_fields.append("description = %s")
            values.append(payload['description'])
        if 'prices' in payload:
            update_fields.append("prices = %s")
            values.append(json.dumps(payload['prices']))
        if 'category' in payload:
            update_fields.append("category = %s")
            values.append(payload['category'])
        if 'allowed_modifiers' in payload:
            update_fields.append("allowed_modifiers = %s")
            values.append(json.dumps(payload['allowed_modifiers']))
        if 'is_available' in payload:
            update_fields.append("is_available = %s")
            values.append(payload['is_available'])

        if not update_fields:
            return {"status": "success", "message": "No data provided to update"}

        values.append(item_id)
        query = f"UPDATE menu_items SET {', '.join(update_fields)} WHERE id = %s"

        cur.execute(query, tuple(values))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()
