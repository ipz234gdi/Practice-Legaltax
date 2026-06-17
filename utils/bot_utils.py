import asyncio
import logging
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

async def safe_send_or_edit(call_func, *args, **kwargs):
    """
    Виконує асинхронний виклик (надсилання чи редагування повідомлення) з автоматичним
    перехопленням Flood Control та повторним викликом після очікування.
    """
    for attempt in range(3):
        try:
            return await call_func(*args, **kwargs)
        except TelegramRetryAfter as e:
            logging.warning(f"Flood control limit hit. Waiting for {e.retry_after} seconds before retry (attempt {attempt + 1}/3).")
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
            logging.error(f"Telegram API Error: {e}")
            raise e
        except Exception as e:
            logging.error(f"Unexpected error in safe call: {e}")
            raise e
    
    # Якщо всі 3 спроби закінчилися невдачею через ретраї (наприклад, через довге очікування)
    logging.error("Failed to execute telegram call after 3 attempts due to rate limit/flood control.")
