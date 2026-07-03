"""
Сервіс тунелювання для автоматичного створення HTTPS тунелю при запуску бота.
Використовує localhost.run (SSH) як основний метод.
Після встановлення тунелю динамічно оновлює TWA_URL у config.
"""

import asyncio
import re
import logging
import config

logger = logging.getLogger("TunnelService")

# Глобальний процес тунелю
_tunnel_process: asyncio.subprocess.Process | None = None
_tunnel_url: str | None = None


async def start_tunnel(port: int = None) -> str | None:
    """
    Запускає SSH тунель через localhost.run і повертає HTTPS URL.
    Якщо TWA_URL вже вказаний і не localhost — використовує його.
    """
    global _tunnel_process, _tunnel_url

    port = port or config.WEB_PORT

    # Якщо в .env вже є нормальний публічний TWA_URL — не запускаємо тунель
    current_twa = config.TWA_URL
    if current_twa and "localhost" not in current_twa and "127.0.0.1" not in current_twa:
        # Перевіряємо чи URL доступний
        if await _check_url_accessible(current_twa):
            logger.info(f"TWA_URL вже налаштований і доступний: {current_twa}")
            return current_twa
        else:
            logger.warning(f"TWA_URL '{current_twa}' недоступний, запускаємо тунель...")

    # Спроба 1: localhost.run (SSH тунель)
    url = await _start_localhost_run(port)

    if url:
        _tunnel_url = url
        twa_url = f"{url}/webapp/"
        config.TWA_URL = twa_url
        logger.info(f"✅ Тунель встановлено! TWA_URL = {twa_url}")
        return twa_url

    logger.error("❌ Не вдалося створити тунель. Mini App може не працювати.")
    return None


async def _check_url_accessible(url: str) -> bool:
    """Перевіряє доступність URL (простий HTTP HEAD запит)."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5), ssl=False) as resp:
                return resp.status < 500
    except Exception:
        # Якщо aiohttp недоступний, пробуємо через urllib
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=5)
            return True
        except Exception:
            return False


async def _start_localhost_run(port: int) -> str | None:
    """
    Запускає тунель через localhost.run за допомогою SSH.
    Парсить URL з виводу SSH.
    """
    global _tunnel_process

    logger.info(f"Запуск тунелю localhost.run на порт {port}...")

    try:
        _tunnel_process = await asyncio.create_subprocess_exec(
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "TCPKeepAlive=yes",
            "-R", f"80:localhost:{port}",
            "nokey@localhost.run",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )

        # Читаємо вивід SSH для пошуку URL
        url = await _parse_tunnel_url(_tunnel_process, timeout=30)

        if url:
            logger.info(f"localhost.run тунель: {url}")
            # Запускаємо фоновий моніторинг процесу
            asyncio.create_task(_monitor_tunnel_process(_tunnel_process, port))
            return url
        else:
            logger.warning("Не вдалося отримати URL від localhost.run")
            if _tunnel_process.returncode is None:
                _tunnel_process.kill()
            return None

    except FileNotFoundError:
        logger.warning("SSH не знайдено в системі")
        return None
    except Exception as e:
        logger.error(f"Помилка запуску localhost.run: {e}")
        return None


async def _parse_tunnel_url(process: asyncio.subprocess.Process, timeout: int = 30) -> str | None:
    """
    Парсить HTTPS URL з виводу процесу тунелю.
    localhost.run видає рядок виду: https://xxxx.lhr.life
    """
    url_pattern = re.compile(r'(https://[a-zA-Z0-9\-]+\.[a-zA-Z0-9\.\-]+)')

    try:
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            if process.returncode is not None:
                # Процес вже завершився — читаємо stderr
                stderr = await process.stderr.read()
                logger.error(f"Тунель завершився передчасно: {stderr.decode(errors='replace')}")
                return None

            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=min(2, end_time - asyncio.get_event_loop().time())
                )
            except asyncio.TimeoutError:
                continue

            if not line:
                continue

            decoded = line.decode(errors='replace').strip()
            if decoded:
                logger.debug(f"Tunnel output: {decoded}")

            match = url_pattern.search(decoded)
            if match:
                url = match.group(1)
                # Фільтруємо URL-адреси, що не є тунельними
                if "twitter.com" not in url and "localhost.run/docs" not in url and "admin.localhost.run" not in url and "localhost:3000" not in url:
                    return url

    except Exception as e:
        logger.error(f"Помилка парсингу URL тунелю: {e}")

    return None


async def _monitor_tunnel_process(process: asyncio.subprocess.Process, port: int):
    """
    Фоновий моніторинг процесу тунелю. Якщо тунель впаде — перезапускає.
    """
    while True:
        try:
            await process.wait()
            logger.warning("⚠️ Тунель впав! Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

            # Перезапускаємо тунель
            new_url = await _start_localhost_run(port)
            if new_url:
                config.TWA_URL = f"{new_url}/webapp/"
                logger.info(f"✅ Тунель перезапущено! Новий TWA_URL = {config.TWA_URL}")
            else:
                logger.error("❌ Не вдалося перезапустити тунель")
                # Чекаємо ще трохи перед повторною спробою
                await asyncio.sleep(30)
                continue

            break  # Моніторинг перейде на новий процес

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Помилка моніторингу тунелю: {e}")
            await asyncio.sleep(10)


async def stop_tunnel():
    """Зупиняє активний тунель."""
    global _tunnel_process, _tunnel_url

    if _tunnel_process and _tunnel_process.returncode is None:
        logger.info("Зупинка тунелю...")
        _tunnel_process.kill()
        try:
            await asyncio.wait_for(_tunnel_process.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

    _tunnel_process = None
    _tunnel_url = None


def get_tunnel_url() -> str | None:
    """Повертає поточний URL тунелю."""
    return _tunnel_url
