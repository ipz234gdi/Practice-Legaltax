import asyncio
import logging
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.base import engine, Base
from handlers import common, cabinet, form, calculator, admin, admin_start
from services.web_server import app
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
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE request_forms ADD COLUMN reply_text VARCHAR(2000)"))
            logger.info("Стовпець reply_text успішно додано до таблиці request_forms.")
        except Exception as e:
            logger.info("Стовпець reply_text вже існує або не може бути створений.")
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
    # ─── 1. Перевірка токенів ───
    if config.USER_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Будь ласка, вкажіть USER_BOT_TOKEN у файлі .env!")
        return

    if config.ADMIN_BOT_TOKEN == "YOUR_ADMIN_BOT_TOKEN_HERE":
        logger.error("❌ Будь ласка, вкажіть ADMIN_BOT_TOKEN у файлі .env!")
        return

    # ─── 2. Ініціалізація бази даних ───
    await init_database()

    # ─── 3. Створення двох ботів ───
    user_bot = Bot(token=config.USER_BOT_TOKEN)
    admin_bot = Bot(token=config.ADMIN_BOT_TOKEN)

    logger.info("✅ Ботів створено:")
    logger.info(f"   👤 Клієнтський бот (user_bot)")
    logger.info(f"   ⚙️  Адмін-бот (admin_bot)")

    # ─── 4. Створення диспетчерів ───
    # Кожен бот має свій диспетчер із окремим сховищем станів
    user_dp = Dispatcher(storage=MemoryStorage())
    admin_dp = Dispatcher(storage=MemoryStorage())

    # ─── 5. Підключення роутерів ───
    # Клієнтський бот: обробники для користувачів
    user_dp.include_router(common.router)      # /start, меню, про нас
    user_dp.include_router(cabinet.router)     # особистий кабінет
    user_dp.include_router(form.router)        # подання заявки
    user_dp.include_router(calculator.router)  # калькулятор податків

    # Адмін-бот: обробники для адміністраторів
    admin_dp.include_router(admin_start.router)  # /start, панель, навігація
    admin_dp.include_router(admin.router)        # черга заявок, callback-кнопки, відповіді

    logger.info("✅ Роутери підключено")

    # ─── 6. Реєструємо ботів у FastAPI ───
    import services.web_server
    services.web_server.user_bot_instance = user_bot
    services.web_server.admin_bot_instance = admin_bot

    # ─── 7. Запуск тунелю для Mini App ───
    logger.info("Перевірка доступності TWA та запуск тунелю...")
    twa_url = await start_tunnel(config.WEB_PORT)
    if twa_url:
        logger.info(f"🌐 Mini App доступний за адресою: {twa_url}")
    else:
        logger.warning("⚠️ Тунель не запущено. Mini App може бути недоступний.")

    # ─── 8. Запуск усіх сервісів паралельно ───
    logger.info("🚀 Запуск ботів та фонових сервісів...")

    try:
        results = await asyncio.gather(
            # Клієнтський бот: polling + передача admin_bot як kwargs до хендлерів
            user_dp.start_polling(user_bot, admin_bot=admin_bot, allowed_updates=user_dp.resolve_used_update_types()),
            # Адмін-бот: polling + передача user_bot як kwargs до хендлерів
            admin_dp.start_polling(admin_bot, user_bot=user_bot, allowed_updates=admin_dp.resolve_used_update_types()),
            # Веб-сервер FastAPI
            start_web_server(),
            return_exceptions=True
        )

        # Логуємо помилки задач, якщо вони були
        task_names = ["UserBot Polling", "AdminBot Polling", "WebServer"]
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Задача {task_names[i]} завершилась з помилкою: {result}")

    except Exception as e:
        logger.critical(f"Критична помилка при роботі додатку: {e}")
    finally:
        await stop_tunnel()
        await user_bot.session.close()
        await admin_bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Боти зупинені.")
