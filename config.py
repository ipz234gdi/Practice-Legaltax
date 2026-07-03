import os
from pathlib import Path
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env, якщо він існує
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- НАЛАШТУВАННЯ TELEGRAM БОТІВ ---
# Токен бота для користувачів (отриманий від @BotFather)
USER_BOT_TOKEN = os.getenv("USER_BOT_TOKEN", os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE"))

# Токен бота для адміністрації (отриманий від @BotFather)
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "YOUR_ADMIN_BOT_TOKEN_HERE")

# Зворотна сумісність: BOT_TOKEN = USER_BOT_TOKEN
BOT_TOKEN = USER_BOT_TOKEN

# ID адміністраторів у Telegram (через кому, наприклад: 123456789,987654321)
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# --- НАЛАШТУВАННЯ БАЗИ ДАНИХ ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/legaltax.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# --- НАЛАШТУВАННЯ ПОШТИ (EMAIL) ---
# Пошта за замовчуванням reiclid@gmail.com
EMAIL_USER = os.getenv("EMAIL_USER", "reiclid@gmail.com")
# Пароль додатку (App Password) для Gmail
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "YOUR_EMAIL_APP_PASSWORD_HERE")
# IMAP сервер для зчитування вхідної пошти
EMAIL_IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
# SMTP сервер для відправки пошти (якщо потрібно буде відправляти відповіді)
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
# Інтервал перевірки пошти у секундах (наприклад, кожні 60 секунд)
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL", "60"))

# --- НАЛАШТУВАННЯ ВЕБ-СЕРВЕРУ (FastAPI) ---
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))

# --- НАЛАШТУВАННЯ САЙТУ ---
SITE_URL = os.getenv("SITE_URL", "https://legaltax.com.ua")
# URL для Telegram Mini App (повинен обов'язково починатися з https://)
TWA_URL = os.getenv("TWA_URL", f"{SITE_URL}/webapp/")

# --- НАЛАШТУВАННЯ АУТЕНТИФІКАЦІЇ ---
# Час дії OTP коду в секундах (5 хвилин)
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
