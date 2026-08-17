# ANCLAV CRM

A microservice-based CRM, loyalty system, and remote ordering platform built for a coffee shop network. 
The system integrates physical POS terminals (aQsi) with Telegram Mini Apps (TMA) and provides a comprehensive analytics dashboard.

## Tech Stack

* **Backend:** Python, FastAPI, Aiogram 3 (Telegram Bot API)
* **Database:** PostgreSQL (raw SQL via `psycopg2`)
* **Frontend:** React, Vite, React Router, Chart.js (Dashboard & TMA)
* **Infrastructure:** Docker, Docker Compose
* **External APIs:** aQsi V4 API (Receipts & Terminals), Open-Meteo API (Weather data)

## Architecture & Services

The application is containerized using Docker Compose and consists of 5 main services:

1. `db`: PostgreSQL database container.
2. `api`: FastAPI REST backend. Handles TMA authentication (via Telegram initData verification), serves analytics data, and manages menu/orders.
3. `bot`: Aiogram-based Telegram bot. Handles FSM for barista operations, shift management, push-notifications for orders, and customer loyalty interactions.
4. `sync`: Background worker syncing receipt data from aQsi POS terminals to the local database for RFM and cohort analysis.
5. `weather`: Background worker collecting hourly weather data for future correlation with sales metrics.

## Key Features

* **Omnichannel Loyalty System:** Automatically links offline purchases (via POS terminal) with online Telegram profiles to calculate RFM segments and cohort retention.
* **Telegram Mini App Ordering:** Guests can order and pay via a React-based TMA. Baristas receive real-time push notifications in the bot when a shift is open.
* **Role-Based Access Control:** Separate flows for `client`, `barista`, and `admin` within the same Telegram Bot interface.
* **Product Analytics Dashboard:** ABC-analysis, cross-sell (basket) analysis, and hourly load charts based on raw transactional data.
* **Automated Feedback Loop:** Scheduled tasks (`asyncio`) request feedback 15 minutes after a confirmed visit and alert the owner on low ratings.

## Local Setup

1. Clone the repository.
2. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```
3. Fill in the required tokens in `.env` (Telegram Bot Token, aQsi Token, Postgres credentials).
4. Run the containers:
   ```bash
   docker-compose up -d --build
   ```

The FastAPI backend will be available at `http://localhost:8000`.
The PostgreSQL database is exposed on port `5433` (as configured in `docker-compose.yml`).

## Project Structure

```text
.
├── BOT.py                  # Telegram bot entry point & handlers
├── api.py                  # FastAPI application & endpoints
├── sync_aqsi.py            # POS synchronization worker
├── weather_worker.py       # Weather data aggregation worker
├── docker-compose.yml      # Container orchestration
├── anclav-dashboard/       # React web app for Admin Analytics
└── anclav-guest-app/       # React web app for Telegram Mini App
```
