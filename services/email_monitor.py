import asyncio
import imaplib
import email
import re
from email.header import decode_header
import logging
from typing import Optional, List, Dict
from database.base import SessionLocal
from database.crud import create_request_form, get_user_by_phone
from handlers.form import notify_admins_new_request
from aiogram import Bot
import config

# Налаштування логування
logger = logging.getLogger("EmailMonitor")


def decode_mime_words(s: Optional[str]) -> str:
    """Декодує заголовки email, такі як тема чи ім'я відправника"""
    if not s:
        return ""
    try:
        parts = decode_header(s)
        decoded_parts = []
        for word, encoding in parts:
            if isinstance(word, bytes):
                if encoding:
                    try:
                        decoded_parts.append(word.decode(encoding))
                    except Exception:
                        decoded_parts.append(word.decode('utf-8', errors='replace'))
                else:
                    decoded_parts.append(word.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(str(word))
        return "".join(decoded_parts)
    except Exception as e:
        logger.error(f"Помилка декодування заголовка: {e}")
        return str(s)


def parse_email_body(msg: email.message.Message) -> str:
    """Рекурсивно витягує текст з тіла листа"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body += part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    body += re.sub('<[^<]+?>', '', html)
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = str(msg.get_payload())

    return body.strip()


def is_legaltax_email(subject: str, sender: str) -> bool:
    """
    Перевіряє, чи є лист від сайту Legal Tax.
    Фільтрує за темою (містить 'Legal Tax') або за відправником.
    """
    subject_lower = subject.lower()
    sender_lower = sender.lower()

    # Перевіряємо тему листа
    if "legal tax" in subject_lower or "legaltax" in subject_lower:
        return True

    # Перевіряємо відправника (Elementor форми з хостингу)
    legaltax_senders = [
        "hosting-55.default-host.net",
        "legaltax.pro",
        "legaltax.com.ua",
    ]
    for domain in legaltax_senders:
        if domain in sender_lower:
            return True

    return False


def parse_legaltax_body(body: str) -> Dict[str, str]:
    """
    Парсить тіло листа від Legal Tax.
    Формат:
        Рядок 1: Ім'я клієнта
        Рядок 2: Номер телефону
        Рядок 3: Опис питання/проблеми
        ---
        Date: ...  (метадані — ігноруються)

    Повертає dict з ключами: name, phone, text
    """
    content = body
    for delimiter in ["---", "--"]:
        if delimiter in content:
            content = content.split(delimiter)[0]
            break

    date_match = re.search(r'^Date:', content, re.MULTILINE | re.IGNORECASE)
    if date_match:
        content = content[:date_match.start()]

    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

    name = lines[0] if len(lines) >= 1 else "Невідомий"
    phone = lines[1] if len(lines) >= 2 else "Не вказано"
    text = lines[2] if len(lines) >= 3 else "Без опису"

    if len(lines) > 3:
        text = "\n".join(lines[2:])

    return {
        "name": name,
        "phone": phone,
        "text": text,
    }


def mark_all_as_seen_sync():
    """
    Позначає ВСІ непрочитані листи як прочитані.
    Викликається один раз при старті бота, щоб не обробляти старі листи.
    """
    if config.EMAIL_PASSWORD == "YOUR_EMAIL_APP_PASSWORD_HERE" or not config.EMAIL_PASSWORD:
        return

    try:
        mail = imaplib.IMAP4_SSL(config.EMAIL_IMAP_SERVER)
        mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status == "OK" and messages[0]:
            count = len(messages[0].split())
            for num in messages[0].split():
                mail.store(num, "+FLAGS", "\\Seen")
            logger.info(f"Позначено {count} старих листів як прочитані (ігноруються).")
        else:
            logger.info("Немає непрочитаних листів при старті.")

        mail.close()
        mail.logout()
    except Exception as e:
        logger.error(f"Помилка при позначенні старих листів: {e}")


def fetch_unseen_emails_sync() -> List[Dict[str, str]]:
    """
    Синхронна функція підключення до пошти та зчитування нових листів.
    Фільтрує тільки листи від сайту Legal Tax.
    """
    if config.EMAIL_PASSWORD == "YOUR_EMAIL_APP_PASSWORD_HERE" or not config.EMAIL_PASSWORD:
        return []

    fetched_emails = []
    try:
        mail = imaplib.IMAP4_SSL(config.EMAIL_IMAP_SERVER)
        mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status == "OK" and messages[0]:
            for num in messages[0].split():
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = decode_mime_words(msg["Subject"])
                sender = decode_mime_words(msg["From"])

                # Фільтруємо: обробляємо тільки листи від Legal Tax
                if not is_legaltax_email(subject, sender):
                    logger.debug(f"Пропускаємо лист від '{sender}' з темою '{subject}' — не від Legal Tax")
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                body = parse_email_body(msg)
                parsed = parse_legaltax_body(body)

                fetched_emails.append({
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "name": parsed["name"],
                    "phone": parsed["phone"],
                    "text": parsed["text"],
                })

                logger.info(
                    f"Оброблено лист Legal Tax: ім'я='{parsed['name']}', "
                    f"телефон='{parsed['phone']}', текст='{parsed['text'][:50]}...'"
                )

                mail.store(num, "+FLAGS", "\\Seen")

        mail.close()
        mail.logout()

    except Exception as e:
        logger.error(f"Помилка при роботі з поштою IMAP: {e}")

    return fetched_emails


async def check_new_emails(admin_bot: Bot):
    """
    Асинхронний метод перевірки нових листів.
    Сповіщення адмінам відправляються через admin_bot.
    """
    emails = await asyncio.to_thread(fetch_unseen_emails_sync)

    for email_data in emails:
        name = email_data["name"]
        phone = email_data["phone"]
        text = email_data["text"]

        logger.info(f"Нова заявка з пошти Legal Tax: {name}, {phone}")

        async with SessionLocal() as session:
            user = await get_user_by_phone(session, phone)
            user_id = user.id if user else None

            req = await create_request_form(
                session=session,
                name=name,
                phone=phone,
                text=text,
                user_id=user_id,
                source="email"
            )
            req_id = req.id

        # Сповіщаємо адмінів через АДМІН-бота
        await notify_admins_new_request(
            bot=admin_bot,
            req_id=req_id,
            name=name,
            phone=phone,
            text=text,
            source="Email (Legal Tax)"
        )


async def email_monitor_loop(admin_bot: Bot):
    """
    Нескінченний асинхронний цикл перевірки вхідних листів.
    admin_bot — бот для надсилання сповіщень адміністраторам.
    """
    logger.info("Запуск фонового моніторингу пошти...")

    await asyncio.to_thread(mark_all_as_seen_sync)

    while True:
        await asyncio.sleep(config.EMAIL_CHECK_INTERVAL)
        await check_new_emails(admin_bot)
