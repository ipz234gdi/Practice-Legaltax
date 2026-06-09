import asyncio
import logging
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.base import engine, Base
from handlers import common, cabinet, form, calculator, admin
from services.web_server import app, bot_instance as ws_bot_instance
from services.email_monitor import email_monitor_loop
from services.tunnel import start_tunnel, stop_tunnel

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("LegalTaxBotMain")

async def init_database():
    """Створює таблиці в базі даних, якщо вони ще не створені"""
    logger.info("Ініціалізація бази даних...")
    async with engine.begin() as conn:
        # Створюємо всі таблиці асинхронно
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Базу даних успішно ініціалізовано.")

async def start_web_server():
    """Запускає веб-сервер FastAPI"""
    logger.info(f"Запуск веб-серверу на {config.WEB_HOST}:{config.WEB_PORT}...")
    uv_config = uvicorn.Config(
        app=app,
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="info",
        loop="asyncio"
    )
    server = uvicorn.Server(uv_config)
    await server.serve()

async def main():
    # 1. Перевірка токена
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Будь ласка, вкажіть ваш BOT_TOKEN у файлі .env або config.py!")
        return

    # 2. Ініціалізація бази даних
    await init_database()

    # 3. Створення об'єктів бота та диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Реєструємо глобальний об'єкт бота для FastAPI сервісів
    import services.web_server
    services.web_server.bot_instance = bot

    # 4. Підключення роутерів (обробників команд)
    # Зверніть увагу на черговість: адмінські хендлери мають бути одними з перших,
    # щоб не перехоплюватися загальними текстовими хендлерами.
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(cabinet.router)
    dp.include_router(form.router)
    dp.include_router(calculator.router)

    # 5. Запуск тунелю для HTTPS доступу до Mini App
    logger.info("Перевірка доступності TWA та запуск тунелю...")
    twa_url = await start_tunnel(config.WEB_PORT)
    if twa_url:
        logger.info(f"🌐 Mini App доступний за адресою: {twa_url}")
    else:
        logger.warning("⚠️ Тунель не запущено. Mini App може бути недоступний.")

    # 6. Запуск фонових задач
    # Запускаємо веб-сервер FastAPI, опитування Telegram бота та моніторинг пошти паралельно
    logger.info("Запуск бота та фонових сервісів...")
    
    try:
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            start_web_server(),
            email_monitor_loop(bot)
        )
        # Логуємо помилки задач, якщо вони були
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_names = ["Polling", "WebServer", "EmailMonitor"]
                logger.error(f"Задача {task_names[i]} завершилась з помилкою: {result}")
    except Exception as e:
        logger.critical(f"Критична помилка при роботі додатку: {e}")
    finally:
        await stop_tunnel()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот зупинений.")

