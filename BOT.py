import os
import logging
import psycopg2
import asyncio
import requests
import uuid
import re
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AQSI_TOKEN = os.getenv("AQSI_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "default_bot")
GROUP_ID = os.getenv("AQSI_GROUP_ID")
OWNER_ID = int(os.getenv("OWNER_ID", 0))

DASHBOARD_URL = os.getenv("DASHBOARD_URL")
GUEST_APP_URL = os.getenv("GUEST_APP_URL")

DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "anclav_crm")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")

DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

TERMINALS = {
    '1010625022006769': 'Калининградская, 1',
    '1010977707053285': 'Ленина, 18'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

pending_referrals = {}

LEVELS = {
    1: "Гость Анклава",
    2: "Друг Анклава",
    3: "Свой человек в Анклаве",
    4: "Анклавный старожил",
    5: "Легенда Анклава",
    6: "Альфа Анклава"
}

LEVEL_PERKS = {
    1: {4: "Печенье с предсказаниями", 7: "Скидка 30% на сезонный напиток", 10: "Бесплатный сезонный напиток"},
    2: {4: "Бесплатный топпинг на выбор", 7: "Скидка 20% на торт или чизкейк", 10: "Бесплатный напиток"},
    3: {4: "Бесплатный дрип пакет", 7: "Скидка 20% на дрипы", 10: "Бесплатный напиток"},
    4: {4: "Бесплатный сэмпл чая", 7: "Скидка 20% на чай", 10: "Бесплатный сезонный напиток"},
    5: {4: "Сэмпл перемолотого зерна", 7: "Скидка 10% на зерно", 10: "Бесплатный напиток вам и другу"}
}

class BaristaFlow(StatesGroup):
    waiting_for_phone = State()
    waiting_for_visits = State()

class FeedbackFlow(StatesGroup):
    waiting_for_comment = State()

def init_db():
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    tg_id BIGINT UNIQUE,
                    username TEXT,
                    phone TEXT,
                    aqsi_client_id TEXT,
                    points INTEGER DEFAULT 0,
                    referrer_tg_id BIGINT,
                    last_visit TEXT
                )
            """)
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'client';")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS loyalty_level INTEGER DEFAULT 1;")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS visits_count INTEGER DEFAULT 0;")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_gifts INTEGER DEFAULT 0;")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_card_migrated BOOLEAN DEFAULT FALSE;")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS active_terminal_id VARCHAR(50);")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS inventory JSONB DEFAULT '{}'::jsonb;")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_queue (
                    id SERIAL PRIMARY KEY,
                    tg_id BIGINT,
                    receipt_id VARCHAR(100),
                    scheduled_time TIMESTAMP,
                    is_sent BOOLEAN DEFAULT FALSE
                )
            """)
            cursor.execute("ALTER TABLE feedback_queue ADD COLUMN IF NOT EXISTS task_type VARCHAR(50) DEFAULT 'feedback';")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    receipt_id VARCHAR(100),
                    tg_id BIGINT,
                    rating INTEGER,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()

def create_aqsi_client(fio, phone):
    clean_phone = str(phone).replace("+", "").replace(" ", "")
    headers = {"x-client-key": f"Application {AQSI_TOKEN}", "Content-Type": "application/json"}
    search_url = "https://api.aqsi.ru/pub/v2/Clients"

    try:
        search_resp = requests.get(search_url, headers=headers, params={"filtered.mainPhone": clean_phone}, timeout=5)
        if search_resp.status_code == 200:
            rows = search_resp.json().get('rows', [])
            if rows:
                return rows[0].get('id'), clean_phone
    except Exception as e:
        logging.error(f"Failed to find aQsi client: {e}")

    create_url = "https://api.aqsi.ru/pub/v2/Clients"
    new_uuid = str(uuid.uuid4())
    payload = {
        "id": new_uuid, "group": {"id": GROUP_ID}, "fio": fio,
        "mainPhone": clean_phone, "comment": "Registration via TG bot"
    }

    try:
        response = requests.post(create_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return new_uuid, clean_phone
        return None, clean_phone
    except Exception as e:
        logging.error(f"Failed to create aQsi client: {e}")
        return None, clean_phone

def get_main_keyboard(role, visits_count=0):
    kb = [
        [KeyboardButton(text="💳 Моя карта"), KeyboardButton(text="🎁 Пригласить друга")]
    ]

    if visits_count > 0 or role in ['admin', 'barista']:
        kb.insert(0, [KeyboardButton(text="☕️ Заказать с собой")])

    if role in ['admin', 'barista']:
        kb.append([KeyboardButton(text="🔍 Проверить гостя"), KeyboardButton(text="💼 Смена")])
    if role == 'admin':
        kb.append([KeyboardButton(text="📊 CRM Дашборд")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

contact_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)]],
    resize_keyboard=True, one_time_keyboard=True
)

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id

    if command.args and command.args.isdigit():
        referrer_id = int(command.args)
        if referrer_id != tg_id:
            pending_referrals[tg_id] = referrer_id

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT loyalty_level, visits_count, phone, role FROM users WHERE tg_id = %s", (tg_id,))
            user = cursor.fetchone()

    if user and user[2]:
        loyalty_level, visits_count, phone, role = user
        visits_count = visits_count or 0
        level_name = LEVELS.get(loyalty_level or 1, "Гость Анклава")
        await message.answer(
            f"Рады видеть вас снова! ☕️\n\n⭐️ Уровень: **{level_name}**\n☕️ Накоплено визитов: **{visits_count}**\n📱 Номер: `{phone}`",
            parse_mode="Markdown", reply_markup=get_main_keyboard(role, visits_count)
        )
    else:
        text = "Добро пожаловать в ANCLAV! ✨\nЗарегистрируйтесь, чтобы получать бесплатные напитки и бонусы."
        if tg_id in pending_referrals:
            text = "Добро пожаловать! ✨\nВы перешли по ссылке друга. Зарегистрируйтесь и получите в подарок **дрип-пакет или сэмпл чая на выбор**!"
        await message.answer(text, parse_mode="Markdown", reply_markup=contact_kb)

@dp.message(F.contact)
async def contact_handler(message: types.Message):
    phone = message.contact.phone_number
    tg_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    fio = message.from_user.first_name

    wait_msg = await message.answer("⏳ Создаем карту в системе кассы...")
    aqsi_id, clean_phone = create_aqsi_client(fio, phone)

    if aqsi_id:
        ref_id = pending_referrals.get(tg_id)
        start_gifts = 1 if ref_id else 0
        initial_inventory = '{"Подарок за друга (Дрип/Чай)": 1}' if start_gifts > 0 else '{}'

        with psycopg2.connect(DB_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (tg_id, username, phone, aqsi_client_id, visits_count, inventory, referrer_tg_id, role)
                    VALUES (%s, %s, %s, %s, 0, %s::jsonb, %s, 'client')
                    ON CONFLICT(tg_id) DO UPDATE SET phone=EXCLUDED.phone, aqsi_client_id=EXCLUDED.aqsi_client_id
                    RETURNING role, visits_count
                """, (tg_id, username, clean_phone, aqsi_id, initial_inventory, ref_id))
                role, visits_count = cursor.fetchone()

                if ref_id:
                    cursor.execute("""
                        UPDATE users
                        SET inventory = COALESCE(inventory, '{}'::jsonb) ||
                                        jsonb_build_object('Подарок за друга (Дрип/Чай)',
                                            COALESCE((inventory->>'Подарок за друга (Дрип/Чай)')::int, 0) + 1)
                        WHERE tg_id = %s
                    """, (ref_id,))
            conn.commit()

        await wait_msg.delete()
        bonus_text = f"\n\n🎁 **Вам начислен подарок за регистрацию!** Заберите дрип-пакет или сэмпл чая на кассе." if start_gifts > 0 else ""
        await message.answer(
            f"✅ Регистрация завершена!{bonus_text}\n\nНазывайте номер `{clean_phone}` бариста при заказе.",
            parse_mode="Markdown", reply_markup=get_main_keyboard(role, visits_count or 0)
        )

        if ref_id:
            try:
                await bot.send_message(ref_id, "🎉 Друг зарегистрировался! При следующем визите не забудьте забрать свой подарок: **дрип-пакет или сэмпл чая**", parse_mode="Markdown")
            except: pass
        pending_referrals.pop(tg_id, None)
    else:
        await wait_msg.delete()
        await message.answer("Ошибка связи с кассой. Попробуйте нажать кнопку еще раз.")

@dp.message(F.text == "💳 Моя карта")
async def show_balance(message: types.Message, state: FSMContext):
    await state.clear()
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT loyalty_level, visits_count, phone, inventory FROM users WHERE tg_id = %s", (message.from_user.id,))
            user = cursor.fetchone()

    if user:
        loyalty_level, visits_count, phone, inventory = user
        loyalty_level = loyalty_level or 1
        visits_count = visits_count or 0
        inventory = inventory or {}

        level_name = LEVELS.get(loyalty_level, "Гость Анклава")

        inv_text = ""
        for item, count in inventory.items():
            if count > 0:
                inv_text += f"• {item}: {count} шт.\n"

        gift_alert = f"\n🎒 **Ваш инвентарь:**\n{inv_text}" if inv_text else "\n🎒 **Ваш инвентарь:** Пока пусто\n"

        if loyalty_level == 6:
            bonus_hint = (
                "👑 **Ваши привилегии Альфа Анклава:**\n"
                "• Скидка 7% на напитки и выпечку\n"
                "• Скидка 3% на чай, зерно и дрипы\n"
                "• Прямая связь с владельцем\n"
                "• Опция «Тайный гость»"
            )
        else:
            cycle_visits = visits_count % 10
            perks = LEVEL_PERKS.get(loyalty_level, LEVEL_PERKS[1])
            if cycle_visits < 4: remains, next_reward = 4 - cycle_visits, perks[4]
            elif cycle_visits < 7: remains, next_reward = 7 - cycle_visits, perks[7]
            else: remains, next_reward = 10 - cycle_visits, perks[10]

            bonus_hint = f"📈 Через **{remains} визита**:\n{next_reward}"

        await message.answer(
            f"💳 **Ваша карта лояльности**\n\n"
            f"📱 Номер: `{phone}`\n"
            f"⭐️ Уровень: **{level_name}**\n"
            f"☕️ Накоплено визитов: **{visits_count}**\n"
            f"{gift_alert}\n"
            f"{bonus_hint}",
            parse_mode="Markdown"
        )

@dp.message(F.text == "🎁 Пригласить друга")
async def invite_friend(message: types.Message, state: FSMContext):
    await state.clear()
    link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"
    await message.answer(
        f"🎁 **Дарите кофе друзьям!**\n\nОтправьте эту ссылку другу. "
        f"Если он зарегистрируется, вы оба получите в подарок **дрип-пакет или сэмпл чая**!\n\n`{link}`",
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def admin_panel_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Открыть дашборд", web_app=WebAppInfo(url=DASHBOARD_URL))]])
    await message.answer("Панель управления администратора:", reply_markup=markup)

@dp.message(F.text == "📊 CRM Дашборд")
async def dashboard_menu_btn_handler(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Открыть дашборд", web_app=WebAppInfo(url=DASHBOARD_URL))]])
    await message.answer("Панель управления администратора:", reply_markup=markup)

@dp.message(F.text == "☕️ Заказать с собой")
async def order_menu_btn_handler(message: types.Message):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role, visits_count FROM users WHERE tg_id = %s", (message.from_user.id,))
            user = cursor.fetchone()

    if user:
        role, visits_count = user
        visits_count = visits_count or 0

        if visits_count > 0 or role in ['admin', 'barista']:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📲 Открыть меню", web_app=WebAppInfo(url=GUEST_APP_URL))]
            ])
            await message.answer("👇 Нажмите кнопку ниже, чтобы собрать заказ:", reply_markup=markup)

@dp.message(F.text == "💼 Смена")
async def shift_management_handler(message: types.Message):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role, active_terminal_id FROM users WHERE tg_id = %s", (message.from_user.id,))
            user = cursor.fetchone()

    if not user or user[0] not in ['admin', 'barista']:
        return

    active_terminal = user[1]

    if active_terminal:
        terminal_name = TERMINALS.get(active_terminal, "Неизвестная точка")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Закрыть смену", callback_data="shift_close")]
        ])
        await message.answer(f"✅ Вы сейчас на смене.\n📍 Точка: **{terminal_name}**\n\nНовые заказы будут приходить вам сюда.", parse_mode="Markdown", reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🟢 Открыть: {name}", callback_data=f"shift_open_{tid}")] for tid, name in TERMINALS.items()
        ])
        await message.answer("💼 У вас закрыта смена. Вы не получаете уведомления о заказах.\n\nГде вы сегодня работаете?", reply_markup=kb)

@dp.callback_query(F.data.startswith("shift_open_"))
async def process_shift_open(callback: types.CallbackQuery):
    terminal_id = callback.data.split("_")[2]

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET active_terminal_id = %s WHERE tg_id = %s", (terminal_id, callback.from_user.id))
        conn.commit()

    terminal_name = TERMINALS.get(terminal_id, "Неизвестная точка")
    await callback.message.edit_text(f"✅ Смена открыта!\n📍 Точка: **{terminal_name}**\n\nВы начнете получать пуши о новых заказах.", parse_mode="Markdown")

@dp.callback_query(F.data == "shift_close")
async def process_shift_close(callback: types.CallbackQuery):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET active_terminal_id = NULL WHERE tg_id = %s", (callback.from_user.id,))
        conn.commit()

    await callback.message.edit_text("🔴 Смена закрыта. Уведомления отключены. Хорошего отдыха!")

@dp.message(F.text == "🔍 Проверить гостя")
async def ask_guest_phone(message: types.Message, state: FSMContext):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM users WHERE tg_id = %s", (message.from_user.id,))
            user = cursor.fetchone()

    if user and user[0] in ['admin', 'barista']:
        await message.answer("📞 Введите номер телефона гостя (например, 79991234567 или 8999...):")
        await state.set_state(BaristaFlow.waiting_for_phone)

@dp.message(StateFilter(BaristaFlow.waiting_for_phone))
async def check_guest_balance(message: types.Message, state: FSMContext):
    phone_input = re.sub(r'\D', '', message.text)
    if phone_input.startswith('8') and len(phone_input) == 11:
        phone_input = '7' + phone_input[1:]

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tg_id, phone, username, last_visit, loyalty_level, visits_count, inventory, is_card_migrated, referrer_tg_id
                FROM users WHERE phone LIKE %s
            """, (f"%{phone_input[-10:]}",))
            guest = cursor.fetchone()

    if guest:
        tg_id, phone, username, last_visit, loyalty_level, visits_count, inventory, is_card_migrated, referrer_tg_id = guest
        loyalty_level = loyalty_level or 1
        visits_count = visits_count or 0
        inventory = inventory or {}

        level_name = LEVELS.get(loyalty_level, "Гость Анклава")
        visit_text = f"\n🕒 Последний визит: {last_visit}" if last_visit else ""
        name_text = f" ({username})" if username else ""

        kb = []
        inv_text = ""

        for item, count in inventory.items():
            if count > 0:
                inv_text += f"\n🎁 {item}: {count} шт."
                kb.append([InlineKeyboardButton(text=f"✅ Выдать: {item[:20]}", callback_data=f"givegift_{tg_id}_{item[:20]}")])

        gift_alert = f"\n\n⚠️ **ДОСТУПНЫЕ БОНУСЫ:**{inv_text}" if inv_text else ""

        if not is_card_migrated and not referrer_tg_id:
            kb.append([InlineKeyboardButton(text="🔄 Оцифровать картонную карту", callback_data=f"migrate_{tg_id}")])

        markup = InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

        await message.answer(
            f"👤 **Гость найден**{name_text}\n"
            f"📱 Номер: `{phone}`\n"
            f"⭐️ Уровень: **{level_name}** ({loyalty_level} ур.)\n"
            f"☕️ Накоплено визитов: **{visits_count}**{visit_text}{gift_alert}",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        await message.answer("❌ Гость с таким номером не найден в системе лояльности.")

    await state.clear()

@dp.callback_query(F.data.startswith("givegift_"))
async def process_give_gift(callback: types.CallbackQuery):
    parts = callback.data.split("_", 2)
    guest_tg_id = parts[1]
    item_name_sliced = parts[2] if len(parts) > 2 else None

    if not item_name_sliced:
        await callback.answer("Ошибка: Товар не найден.", show_alert=True)
        return

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT inventory FROM users WHERE tg_id = %s", (guest_tg_id,))
            res = cursor.fetchone()

            if res and res[0]:
                inventory = res[0]
                real_item_name = next((k for k in inventory.keys() if k.startswith(item_name_sliced)), None)

                if real_item_name and inventory.get(real_item_name, 0) > 0:
                    inventory[real_item_name] -= 1
                    cursor.execute("UPDATE users SET inventory = %s WHERE tg_id = %s", (json.dumps(inventory), guest_tg_id))
                    conn.commit()

                    await callback.message.edit_text(callback.message.text + f"\n\n✅ *Списан 1 шт.: {real_item_name}!*", parse_mode="Markdown")
                    try:
                        await bot.send_message(guest_tg_id, f"🎁 Вы забрали свой бонус ({real_item_name})! Наслаждайтесь!")
                    except: pass
                else:
                    await callback.answer("❌ У гостя закончился этот бонус.", show_alert=True)
            else:
                await callback.answer("❌ Инвентарь гостя пуст.", show_alert=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, state: FSMContext):
    _, receipt_id, rating_str = callback.data.split("_", 2)
    rating = int(rating_str)
    tg_id = callback.from_user.id

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO feedback (receipt_id, tg_id, rating)
                VALUES (%s, %s, %s)
            """, (receipt_id, tg_id, rating))
        conn.commit()

    await state.update_data(receipt_id=receipt_id)

    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_comment")]
    ])

    await callback.message.edit_text(
        f"✅ Вы поставили {rating} ⭐️. Спасибо!\n\n"
        f"Если хотите, напишите пару слов о вашем визите (что понравилось или что стоит улучшить) в ответном сообщении или нажмите «Пропустить»:",
        reply_markup=skip_kb
    )
    await callback.answer()
    await state.set_state(FeedbackFlow.waiting_for_comment)

@dp.callback_query(F.data == "skip_comment", StateFilter(FeedbackFlow.waiting_for_comment))
async def skip_comment_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✅ Спасибо за вашу оценку! Ждем вас снова ☕️")
    await state.clear()

@dp.message(StateFilter(FeedbackFlow.waiting_for_comment))
async def save_text_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    receipt_id = data.get("receipt_id")

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE feedback
                SET comment = %s
                WHERE receipt_id = %s AND tg_id = %s
                RETURNING rating
            """, (message.text, receipt_id, message.from_user.id))
            res = cursor.fetchone()
            rating = res[0] if res else None

            terminal_id, cashier_name = "Неизвестно", "Неизвестно"
            items_data = []

            if rating and rating <= 3:
                cursor.execute("SELECT terminal_id, cashier_name FROM receipts WHERE receipt_id = %s", (receipt_id,))
                receipt_info = cursor.fetchone()
                if receipt_info:
                    terminal_id, cashier_name = receipt_info

                cursor.execute("SELECT item_name, quantity FROM receipt_items WHERE receipt_id = %s", (receipt_id,))
                items_data = cursor.fetchall()
        conn.commit()

    await message.answer("✅ Отзыв успешно сохранен. Благодаря вам мы становимся лучше!")
    await state.clear()

    if rating and rating <= 3 and OWNER_ID:
        terminal_name = TERMINALS.get(terminal_id, terminal_id)
        items_text = ""
        if items_data:
            for item_name, qty in items_data:
                items_text += f"• {item_name} (x{int(qty)})\n"
        else:
            items_text = "Данные о составе заказа отсутствуют\n"

        admin_msg = (
            f"⚠️ **Низкая оценка от гостя!**\n"
            f"⭐️ Оценка: **{rating}/5**\n"
            f"💬 Комментарий: _{message.text}_\n\n"
            f"📍 Точка: **{terminal_name}**\n"
            f"🧑‍🍳 Бариста: **{cashier_name}**\n\n"
            f"☕️ **Состав заказа:**\n{items_text}\n"
            f"👤 Гость ID: `{message.from_user.id}`\n"
            f"🧾 Чек: `{receipt_id}`"
        )
        try:
            await bot.send_message(OWNER_ID, admin_msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send feedback notification: {e}")

@dp.callback_query(F.data.startswith("migrate_"))
async def start_migration(callback: types.CallbackQuery, state: FSMContext):
    guest_tg_id = callback.data.split("_")[1]
    await state.update_data(guest_tg_id=guest_tg_id)

    kb = []
    for lvl_num, lvl_name in LEVELS.items():
        kb.append([InlineKeyboardButton(text=f"{lvl_num}. {lvl_name}", callback_data=f"setlvl_{lvl_num}")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text("Выберите уровень, который указан на картонной карточке гостя:", reply_markup=markup)

@dp.callback_query(F.data.startswith("setlvl_"))
async def set_migration_level(callback: types.CallbackQuery, state: FSMContext):
    level = int(callback.data.split("_")[1])
    await state.update_data(new_level=level)

    await callback.message.edit_text(f"✅ Уровень {level} выбран.\n\nВведите количество печатей (визитов), проставленных на карточке (просто число):")
    await state.set_state(BaristaFlow.waiting_for_visits)

@dp.message(StateFilter(BaristaFlow.waiting_for_visits))
async def save_migrated_card(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите только число.")
        return

    visits = int(message.text)
    data = await state.get_data()
    guest_tg_id = data.get("guest_tg_id")
    new_level = data.get("new_level")

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users
                SET loyalty_level = %s, visits_count = %s, is_card_migrated = TRUE
                WHERE tg_id = %s
            """, (new_level, visits, guest_tg_id))
        conn.commit()

    level_name = LEVELS.get(new_level, "Гость Анклава")
    await message.answer(f"✅ Данные успешно перенесены!\n\nГостю присвоен уровень: **{level_name}**\nВизитов зафиксировано: **{visits}**", parse_mode="Markdown")

    try:
        await bot.send_message(
            guest_tg_id,
            f"🎉 Ваши данные с картонной карточки успешно перенесены в систему!\n\n⭐️ Ваш уровень: **{level_name}**\n☕️ Накоплено визитов: **{visits}**",
            parse_mode="Markdown"
        )
    except Exception: pass
    await state.clear()

@dp.callback_query(F.data.startswith("ord_acc_"))
async def handle_order_accept(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]
    barista_name = callback.from_user.first_name

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orders SET status = 'accepted' WHERE id = %s RETURNING tg_id", (order_id,))
            res = cursor.fetchone()
            guest_tg_id = res[0] if res else None
        conn.commit()

    new_text = callback.message.text + f"\n\n👨‍🍳 **Принял в работу:** {barista_name}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔥 Готово к выдаче", callback_data=f"ord_rdy_{order_id}")]])
    await callback.message.edit_text(new_text, reply_markup=kb, parse_mode="Markdown")

    if guest_tg_id:
        try:
            await bot.send_message(guest_tg_id, f"🧑‍🍳 Ваш заказ **#{order_id}** принят и уже готовится!", parse_mode="Markdown")
        except Exception: pass

@dp.callback_query(F.data.startswith("ord_rdy_"))
async def handle_order_ready(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orders SET status = 'ready' WHERE id = %s RETURNING tg_id", (order_id,))
            res = cursor.fetchone()
            guest_tg_id = res[0] if res else None
        conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Выдан гостю", callback_data=f"ord_cmp_{order_id}")]])
    await callback.message.edit_reply_markup(reply_markup=kb)

    if guest_tg_id:
        try:
            await bot.send_message(guest_tg_id, f"☕️ Ваш заказ **#{order_id}** готов! Назовите этот номер на кассе.", parse_mode="Markdown")
        except Exception: pass

@dp.callback_query(F.data.startswith("ord_cmp_"))
async def handle_order_complete(callback: types.CallbackQuery):
    order_id = callback.data.split("_")[2]

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orders SET status = 'completed' WHERE id = %s", (order_id,))
        conn.commit()

    new_text = callback.message.text.replace("👨‍🍳", "✅") + "\n\n🏁 *Заказ закрыт*"
    await callback.message.edit_text(new_text, parse_mode="Markdown")

async def feedback_scheduler():
    while True:
        try:
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, tg_id, receipt_id, task_type
                        FROM feedback_queue
                        WHERE scheduled_time <= NOW() AND is_sent = FALSE
                        ORDER BY id ASC
                    """)
                    tasks = cursor.fetchall()

                    tasks_by_user = {}
                    for t_id, tg_id, r_id, t_type in tasks:
                        if tg_id not in tasks_by_user:
                            tasks_by_user[tg_id] = {'visits': [], 'feedbacks': []}
                        if t_type == 'visit':
                            tasks_by_user[tg_id]['visits'].append(t_id)
                        elif t_type == 'feedback':
                            tasks_by_user[tg_id]['feedbacks'].append((t_id, r_id))

                    for tg_id, user_tasks in tasks_by_user.items():
                        try:
                            cursor.execute("SELECT loyalty_level, visits_count, inventory FROM users WHERE tg_id = %s", (tg_id,))
                            user_res = cursor.fetchone()
                            if not user_res:
                                continue

                            loyalty_level, visits_count, inventory = user_res
                            loyalty_level = loyalty_level or 1
                            visits_count = visits_count or 0
                            inventory = inventory or {}

                            visit_ids = user_tasks['visits']
                            if visit_ids:
                                num_visits = len(visit_ids)
                                perks = LEVEL_PERKS.get(loyalty_level, LEVEL_PERKS[1])
                                earned_rewards = []
                                start_v = max(1, visits_count - num_visits + 1)

                                for v in range(start_v, visits_count + 1):
                                    cv = v % 10
                                    if cv in [4, 7] or (v > 0 and cv == 0):
                                        rw = 10 if cv == 0 else cv
                                        earned = perks[rw]
                                        earned_rewards.append(earned)
                                        inventory[earned] = inventory.get(earned, 0) + 1

                                if earned_rewards:
                                    cursor.execute("UPDATE users SET inventory = %s WHERE tg_id = %s", (json.dumps(inventory), tg_id))

                                cycle_visits = visits_count % 10
                                if loyalty_level == 6:
                                    bonus_hint = "👑 **Ваши привилегии Альфа Анклава активны!**"
                                else:
                                    if cycle_visits < 4: remains, next_reward = 4 - cycle_visits, perks[4]
                                    elif cycle_visits < 7: remains, next_reward = 7 - cycle_visits, perks[7]
                                    else: remains, next_reward = 10 - cycle_visits, perks[10]
                                    bonus_hint = f"📈 Через **{remains} визита** вы получите:\n{next_reward}"

                                inv_text = "\n".join([f"• {k}: {v} шт." for k, v in inventory.items() if v > 0])
                                if not inv_text: inv_text = "Пока пусто"

                                alert = f"🎉 **Вы достигли чекпоинта!**\nДобавлено в инвентарь: {', '.join(earned_rewards)}\n\n" if earned_rewards else ""
                                msg_text = (
                                    f"✅ **Визит успешно засчитан!**\n"
                                    f"☕️ Накоплено визитов: **{visits_count}**\n\n"
                                    f"{alert}🎒 **Ваш инвентарь (доступные бонусы):**\n{inv_text}\n\n{bonus_hint}"
                                )

                                try:
                                    await bot.send_message(tg_id, msg_text, parse_mode="Markdown")
                                except Exception as e:
                                    logging.error(f"Failed to send visit push to {tg_id}: {e}")

                                cursor.execute("UPDATE feedback_queue SET is_sent = TRUE WHERE id = ANY(%s)", (visit_ids,))
                                conn.commit()

                            for f_task_id, r_id in user_tasks['feedbacks']:
                                kb = InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text=f"{i} ⭐️", callback_data=f"rate_{r_id}_{i}") for i in range(1, 6)]
                                ])
                                try:
                                    await bot.send_message(tg_id, "☕️ Спасибо, что зашли к нам сегодня! Пожалуйста, оцените ваш визит:", reply_markup=kb)
                                except Exception as e:
                                    logging.error(f"Failed to send feedback request to {tg_id}: {e}")

                                cursor.execute("UPDATE feedback_queue SET is_sent = TRUE WHERE id = %s", (f_task_id,))
                                conn.commit()

                        except Exception as e:
                            conn.rollback()
                            logging.error(f"Task processing failed for {tg_id}: {e}")

        except Exception as e:
            logging.error(f"Feedback scheduler error: {e}")

        await asyncio.sleep(3)

async def order_notification_scheduler():
    while True:
        try:
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, tg_id, terminal_id, total_amount
                        FROM orders
                        WHERE is_notified = FALSE
                    """)
                    new_orders = cursor.fetchall()

                    for order in new_orders:
                        order_id, guest_tg_id, terminal_id, total = order

                        cursor.execute("""
                            SELECT mi.name, oi.quantity, oi.modifiers
                            FROM order_items oi
                            JOIN menu_items mi ON oi.menu_item_id = mi.id
                            WHERE oi.order_id = %s
                        """, (order_id,))
                        items = cursor.fetchall()

                        items_text = ""
                        for item_name, qty, modifiers in items:
                            mod_str = ""
                            if modifiers:
                                mod_str = f" ({', '.join(str(v) for v in modifiers.values())})"
                            items_text += f"• {item_name}{mod_str} x{qty}\n"

                        terminal_name = TERMINALS.get(terminal_id, "Неизвестная точка")

                        msg_text = (
                            f"🔔 **НОВЫЙ ПРЕДЗАКАЗ #{order_id}**\n"
                            f"📍 {terminal_name}\n"
                            f"👤 Гость ID: `{guest_tg_id}`\n\n"
                            f"**Состав:**\n{items_text}\n"
                            f"💰 Сумма: **{total} ₽**"
                        )

                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="✅ Принять в работу", callback_data=f"ord_acc_{order_id}")]
                        ])

                        cursor.execute("SELECT tg_id FROM users WHERE active_terminal_id = %s", (terminal_id,))
                        baristas = cursor.fetchall()

                        sent_count = 0
                        for (barista_id,) in baristas:
                            try:
                                await bot.send_message(barista_id, msg_text, parse_mode="Markdown", reply_markup=kb)
                                sent_count += 1
                            except Exception as e:
                                logging.error(f"Failed to send order to barista {barista_id}: {e}")

                        if sent_count == 0 and GROUP_ID:
                            try:
                                await bot.send_message(GROUP_ID, f"⚠️ *ОТКРЫТЫХ СМЕН НЕТ*\n{msg_text}", parse_mode="Markdown", reply_markup=kb)
                            except Exception: pass

                        cursor.execute("UPDATE orders SET is_notified = TRUE WHERE id = %s", (order_id,))
                        conn.commit()

        except Exception as e:
            logging.error(f"Order scheduler error: {e}")

        await asyncio.sleep(5)

async def on_startup(bot: Bot):
    asyncio.create_task(feedback_scheduler())
    asyncio.create_task(order_notification_scheduler())

if __name__ == "__main__":
    init_db()
    dp.startup.register(on_startup)
    logging.info("Starting bot...")
    dp.run_polling(bot)
