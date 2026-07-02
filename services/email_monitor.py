import asyncio
import imaplib
import email
from email.header import decode_header
import logging
from typing import Optional, Tuple, List, Dict
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
                # Якщо немає plain text, беремо html як запасний варіант
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    # Просте очищення від HTML тегів (для ТГ цього вистачить)
                    import re
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
    Буде виконуватися у фоновому потоці через asyncio.to_thread.
    """
    if config.EMAIL_PASSWORD == "YOUR_EMAIL_APP_PASSWORD_HERE" or not config.EMAIL_PASSWORD:
        return []

    fetched_emails = []
    try:
        # Підключаємося до IMAP
        mail = imaplib.IMAP4_SSL(config.EMAIL_IMAP_SERVER)
        mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        mail.select("inbox")
        
        # Шукаємо нечитані листи
        status, messages = mail.search(None, "UNSEEN")
        if status == "OK" and messages[0]:
            for num in messages[0].split():
                # Отримуємо заголовок та тіло листа
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    continue
                    
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Декодуємо дані листа
                subject = decode_mime_words(msg["Subject"])
                sender = decode_mime_words(msg["From"])
                body = parse_email_body(msg)
                
                fetched_emails.append({
                    "sender": sender,
                    "subject": subject,
                    "body": body
                })
                
                # Відзначаємо лист як прочитаний
                mail.store(num, "+FLAGS", "\\Seen")
                
        mail.close()
        mail.logout()
        
    except Exception as e:
        logger.error(f"Помилка при роботі з поштою IMAP: {e}")
        
    return fetched_emails

async def check_new_emails(bot: Bot):
    """
    Асинхронний метод, що викликає синхронний фетч пошти у потоці,
    а потім асинхронно записує листи у БД та сповіщає адміністраторів.
    """
    # Запускаємо блокуючі операції IMAP в окремому потоці
    emails = await asyncio.to_thread(fetch_unseen_emails_sync)
    
    for email_data in emails:
        sender = email_data["sender"]
        subject = email_data["subject"]
        body = email_data["body"]
        
        logger.info(f"Отримано новий лист від {sender} з темою '{subject}'")
        
        # Створюємо опис для заявки
        request_text = f"Тема: {subject}\n\nТекст листа:\n{body}"
        
        # Спробуємо зберегти це як заявку в БД
        async with SessionLocal() as session:
            # Оскільки телефону в листі може не бути, вказуємо пошту відправника як телефон або створюємо заглушку
            phone_placeholder = sender
            name_placeholder = sender.split("<")[0].strip() if "<" in sender else sender
            
            # Шукаємо користувача за email як телефоном (якщо раптом зареєстрований)
            user = await get_user_by_phone(session, phone_placeholder)
            user_id = user.id if user else None
            
            req = await create_request_form(
                session=session,
                name=name_placeholder,
                phone=phone_placeholder,
                text=request_text,
                user_id=user_id,
                source="email"
            )
            req_id = req.id
            
        # Сповіщаємо адмінів
        await notify_admins_new_request(
            bot=bot,
            req_id=req_id,
            name=name_placeholder,
            phone=phone_placeholder,
            text=request_text,
            source="Email Пошта"
        )

async def email_monitor_loop(bot: Bot):
    """
    Нескінченний асинхронний цикл перевірки вхідних листів
    """
    logger.info("Запуск фонового моніторингу пошти...")

    # При старті позначаємо ВСІ старі листи як прочитані
    await asyncio.to_thread(mark_all_as_seen_sync)

    while True:
        # Чекаємо інтервал ПЕРЕД першою перевіркою, щоб нові листи мали час надійти
        await asyncio.sleep(config.EMAIL_CHECK_INTERVAL)
        await check_new_emails(bot)
