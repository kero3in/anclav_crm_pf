import os
import time
import requests
import psycopg2
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("POSTGRES_DB", "anclav_crm")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

# Координаты и смещение времени по умолчанию установлены для Калининградской области,
# но могут быть переопределены через переменные окружения.
LAT = os.getenv("WEATHER_LAT", "54.6386")
LON = os.getenv("WEATHER_LON", "21.8123")
TIMEZONE_OFFSET = int(os.getenv("TIMEZONE_OFFSET_HOURS", 2))

WMO_CODE_MAP = {
    0: "Clear", 1: "Clouds", 2: "Clouds", 3: "Clouds",
    45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 56: "Drizzle", 57: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Rain", 66: "Rain", 67: "Rain",
    71: "Snow", 73: "Snow", 75: "Snow", 77: "Snow",
    80: "Rain", 81: "Rain", 82: "Rain", 85: "Snow", 86: "Snow",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"
}

def get_condition_name(code):
    return WMO_CODE_MAP.get(code, "Unknown")

def init_db():
    with psycopg2.connect(host=DB_HOST, port="5432", database=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS weather_log (
                    id SERIAL PRIMARY KEY,
                    recorded_at TIMESTAMP UNIQUE NOT NULL,
                    temperature NUMERIC(5, 2),
                    feels_like NUMERIC(5, 2),
                    condition VARCHAR(50),
                    wind_speed NUMERIC(5, 2),
                    precipitation NUMERIC(5, 2),
                    humidity INTEGER
                )
            ''')
        conn.commit()
    logging.info("Weather database table initialized.")

def fetch_weather():
    local_time = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)

    if not (8 <= local_time.hour <= 20):
        logging.info("Outside working hours. Weather fetch skipped.")
        return

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={LAT}&longitude={LON}&"
            f"current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation,relative_humidity_2m&"
            f"timezone=auto"
        )

        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            logging.error(f"Open-Meteo API Error: {res.status_code} - {res.text}")
            return

        data = res.json().get('current', {})

        temp = data.get('temperature_2m')
        feels_like = data.get('apparent_temperature')
        weather_code = data.get('weather_code', 0)
        wind_speed = data.get('wind_speed_10m', 0)
        precipitation = data.get('precipitation', 0)
        humidity = data.get('relative_humidity_2m', 0)

        condition = get_condition_name(weather_code)
        current_hour = local_time.replace(minute=0, second=0, microsecond=0)

        with psycopg2.connect(host=DB_HOST, port="5432", database=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO weather_log (recorded_at, temperature, feels_like, condition, wind_speed, precipitation, humidity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (recorded_at) DO NOTHING
                """, (current_hour, temp, feels_like, condition, wind_speed, precipitation, humidity))
            conn.commit()

        logging.info(f"Weather updated: {temp}C, {condition}, Precipitation: {precipitation}mm, Humidity: {humidity}%")

    except Exception as e:
        logging.error(f"Weather fetch failed: {e}")

if __name__ == "__main__":
    logging.info("Weather worker started.")
    time.sleep(10)
    init_db()

    while True:
        fetch_weather()
        time.sleep(3600)
