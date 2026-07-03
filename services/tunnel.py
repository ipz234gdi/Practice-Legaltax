"""
Сервіс конфігурації URL для Telegram Mini App.
Використовує TWA_URL з конфігурації (встановлений через .env).
Автоматичне створення тунелю видалено за запитом користувача.
"""

import logging
import config

logger = logging.getLogger("TunnelService")


async def start_tunnel(port: int = None) -> str | None:
    """
    Повертає сконфігурований TWA_URL з файлу конфігурації.
    Автоматичне створення тунелів повністю вимкнено.
    """
    twa_url = config.TWA_URL
    if twa_url:
        logger.info(f"Використовується TWA_URL з конфігурації: {twa_url}")
        return twa_url
    else:
        logger.warning("⚠️ TWA_URL не вказано у файлі конфігурації (.env)!")
        return None


async def stop_tunnel():
    """Заглушка для сумісності з основним кодом."""
    pass


def get_tunnel_url() -> str | None:
    """Повертає поточний URL."""
    return config.TWA_URL
