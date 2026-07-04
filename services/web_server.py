import random
import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from database.base import SessionLocal
from database.crud import get_user_by_phone, create_request_form, create_auth_session, verify_otp_code, get_user_requests, get_user_by_id
from database.models import RequestForm
from handlers.form import notify_admins_new_request
from aiogram import Bot
from sqlalchemy import select, func
import logging

app = FastAPI(title="LegalTax Bot API", version="1.0.0")

# CORS для Telegram Mini Apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Повертає статус для перевірки працездатності (Health Check)"""
    return {"status": "ok", "message": "LegalTax Bot API is running"}

# Монтуємо статичні файли Mini App
webapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")
if os.path.isdir(webapp_dir):
    app.mount("/webapp", StaticFiles(directory=webapp_dir, html=True), name="webapp")

# Глобальні об'єкти ботів, ініціалізуються при старті
user_bot_instance: Optional[Bot] = None
admin_bot_instance: Optional[Bot] = None


def get_user_bot() -> Bot:
    """Повертає клієнтського бота для відправки повідомлень користувачам."""
    if user_bot_instance is None:
        raise HTTPException(status_code=500, detail="User bot instance not initialized yet")
    return user_bot_instance


def get_admin_bot() -> Bot:
    """Повертає адмін-бота для сповіщень адмінам."""
    if admin_bot_instance is None:
        raise HTTPException(status_code=500, detail="Admin bot instance not initialized yet")
    return admin_bot_instance


# Схеми запитів Pydantic
class WebLeadSchema(BaseModel):
    name: str = Field(..., example="Олександр")
    phone: str = Field(..., example="+380501234567")
    text: str = Field(..., example="Потрібна консультація щодо ФОП")

class SendOTPSchema(BaseModel):
    phone: str = Field(..., example="+380501234567")

class VerifyOTPSchema(BaseModel):
    phone: str = Field(..., example="+380501234567")
    code: str = Field(..., example="123456")

class TWACreateRequestSchema(BaseModel):
    user_id: int
    name: str
    phone: str
    text: str

class TWAAdminActionSchema(BaseModel):
    admin_id: int
    request_id: int
    action: str  # accept, reject, reply
    reply_text: Optional[str] = None


@app.post("/api/web-lead")
async def receive_web_lead(
    request: Request,
    admin_bot: Bot = Depends(get_admin_bot)
):
    """
    Приймає заявки з сайту LegalTax та пересилає їх адмінам через адмін-бота.
    Підтримує:
    1. Прямий плоский JSON.
    2. Elementor JSON (form_fields).
    3. Elementor URL-encoded form data (стандартний формат Elementor webhook).
    """
    content_type = request.headers.get("content-type", "").lower()
    
    name = ""
    phone = ""
    text = ""
    all_fields = {}
    
    # 1. Зчитуємо URL-encoded або Form-data
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form_data = await request.form()
            all_fields.update(dict(form_data))
        except Exception as e:
            logging.error(f"Помилка читання form data: {e}")
            
    # 2. Зчитуємо JSON
    else:
        try:
            json_data = await request.json()
            if isinstance(json_data, dict):
                all_fields.update(json_data)
                form_fields = json_data.get("form_fields", {})
                if isinstance(form_fields, dict):
                    all_fields.update(form_fields)
        except Exception as e:
            logging.error(f"Помилка читання JSON data: {e}")

    # Виводимо отриманий вебхук у лог для налагодження
    logging.info(f"⚡ [WEBHOOK] Отримано запит з сайту. Content-Type: {content_type}")
    logging.info(f"⚡ [WEBHOOK] Всі розпарсені поля: {all_fields}")

    # Спроба знайти поля за назвами ключів
    for k, v in all_fields.items():
        if not isinstance(v, str):
            continue
        v_val = v.strip()
        if not v_val:
            continue
            
        k_lower = k.lower()
        
        # Ігноруємо технічні метадані Elementor та дати/час
        if k_lower in [
            "form_name", "form_id", "post_id", "date", "time", 
            "user agent", "user_agent", "remote ip", "remote_ip", 
            "powered by", "page url", "page_url", "referer", "url"
        ]:
            continue
            
        if k_lower == "lt_t_val" or k_lower == "tel" or "tel" in k_lower or "phone" in k_lower or "number" in k_lower:
            phone = v_val
        elif k_lower == "lt_n_val" or k_lower == "name" or "name" in k_lower or "ім'" in k_lower or "імя" in k_lower or "имя" in k_lower or k_lower == "ім" or k_lower.startswith("ім ") or k_lower.endswith(" ім") or " ім " in k_lower:
            # Уникаємо запису form_name, time або date як імені користувача
            if "form" not in k_lower and "time" not in k_lower and "date" not in k_lower:
                name = v_val
        elif k_lower == "lt_m_val" or k_lower == "message" or "text" in k_lower or "mess" in k_lower or "пита" in k_lower or "ques" in k_lower or "зап" in k_lower:
            text = v_val

    # Якщо телефон не знайдено за назвою ключа, шукаємо за форматом значення
    if not phone:
        for k, v in all_fields.items():
            if not isinstance(v, str):
                continue
            v_val = v.strip()
            k_lower = k.lower()
            if k_lower in [
                "form_name", "form_id", "post_id", "date", "time", 
                "user agent", "user_agent", "remote ip", "remote_ip", 
                "powered by", "page url", "page_url", "referer", "url"
            ] or "form" in k_lower or "time" in k_lower or "date" in k_lower:
                continue
            # Залишаємо лише цифри
            clean_digits = "".join(filter(str.isdigit, v_val))
            if 9 <= len(clean_digits) <= 15:
                phone = v_val
                break

    # Якщо ім'я не знайдено, беремо будь-яке коротке текстове поле, яке не є телефоном і не метаданими
    if not name:
        for k, v in all_fields.items():
            if not isinstance(v, str):
                continue
            v_val = v.strip()
            k_lower = k.lower()
            if k_lower in [
                "form_name", "form_id", "post_id", "date", "time", 
                "user agent", "user_agent", "remote ip", "remote_ip", 
                "powered by", "page url", "page_url", "referer", "url"
            ] or "form" in k_lower or "time" in k_lower or "date" in k_lower:
                continue
            if v_val == phone or not v_val:
                continue
            if len(v_val) < 40 and v_val != text:
                name = v_val
                break

    # Якщо текст не знайдено, беремо перше довше поле
    if not text:
        for k, v in all_fields.items():
            if not isinstance(v, str):
                continue
            v_val = v.strip()
            k_lower = k.lower()
            if k_lower in [
                "form_name", "form_id", "post_id", "date", "time", 
                "user agent", "user_agent", "remote ip", "remote_ip", 
                "powered by", "page url", "page_url", "referer", "url"
            ] or "form" in k_lower or "time" in k_lower or "date" in k_lower:
                continue
            if v_val == phone or v_val == name or not v_val:
                continue
            text = v_val
            break

    if not name:
        name = "Клієнт з сайту"
    if not phone:
        logging.error(f"Не вдалося знайти телефон. Отримані поля: {all_fields}")
        raise HTTPException(status_code=400, detail="Phone number is required")

    async with SessionLocal() as session:
        user = await get_user_by_phone(session, phone)
        user_id = user.id if user else None

        req = await create_request_form(
            session=session,
            name=name,
            phone=phone,
            text=text,
            user_id=user_id,
            source="site"
        )
        req_id = req.id

    # Сповіщаємо адмінів у фоновому режимі (щоб уникнути таймауту на стороні Elementor)
    import asyncio
    asyncio.create_task(
        notify_admins_new_request(admin_bot, req_id, name, phone, text, "Сайт LegalTax")
    )

    return {"status": "success", "request_id": req_id}


@app.post("/api/send-otp")
async def send_otp(
    data: SendOTPSchema,
    user_bot: Bot = Depends(get_user_bot)
):
    """
    Генерує 6-значний код і відправляє його користувачу через клієнтський бот
    """
    phone = data.phone

    async with SessionLocal() as session:
        user = await get_user_by_phone(session, phone)
        if not user:
            return {
                "status": "user_not_found",
                "message": "Користувач з таким номером не запускав бота LegalTax. Будь ласка, запустіть бота спочатку."
            }

        code = str(random.randint(100000, 999999))
        await create_auth_session(session, phone, code)

    # Надсилаємо код користувачу через клієнтський бот
    try:
        message_text = (
            f"🔑 *Код авторизації для сайту LegalTax*\n\n"
            f"Ваш одноразовий код підтвердження:\n"
            f"⚡ `{code}` ⚡\n\n"
            f"⚠️ _Не передавайте цей код нікому\\._"
        )
        await user_bot.send_message(
            chat_id=user.id,
            text=message_text,
            parse_mode="MarkdownV2"
        )
        return {"status": "sent", "phone": phone}
    except Exception as e:
        logging.error(f"Не вдалося надіслати OTP код користувачу {user.id}: {e}")
        return {"status": "error", "message": "Не вдалося надіслати код у Telegram"}


@app.post("/api/verify-otp")
async def verify_otp(data: VerifyOTPSchema):
    """
    Перевіряє правильність введеного коду на сайті
    """
    async with SessionLocal() as session:
        is_valid = await verify_otp_code(session, data.phone, data.code)

    if is_valid:
        return {"status": "verified"}
    else:
        return {"status": "invalid", "message": "Неправильний або застарілий код"}


# ============================================================
# --- TELEGRAM MINI APP (TWA) API ---
# ============================================================

@app.get("/api/twa/my-requests")
async def twa_get_my_requests(user_id: int):
    """
    Повертає список заявок користувача для Telegram Mini App
    """
    async with SessionLocal() as session:
        result = await session.execute(
            select(RequestForm)
            .where(RequestForm.user_id == user_id)
            .order_by(RequestForm.created_at.desc())
            .limit(20)
        )
        requests = result.scalars().all()

    return [
        {
            "id": req.id,
            "name": req.name,
            "phone": req.phone,
            "text": req.text,
            "status": req.status,
            "source": req.source,
            "reply_text": req.reply_text,
            "created_at": (req.created_at.isoformat() + "Z") if req.created_at else None
        }
        for req in requests
    ]


@app.post("/api/twa/create-request")
async def twa_create_request(
    data: TWACreateRequestSchema,
    admin_bot: Bot = Depends(get_admin_bot)
):
    """
    Створює нову заявку від користувача Telegram Mini App
    """
    async with SessionLocal() as session:
        req = await create_request_form(
            session=session,
            name=data.name,
            phone=data.phone,
            text=data.text,
            user_id=data.user_id,
            source="bot"
        )
        req_id = req.id

    # Сповіщаємо адмінів через адмін-бота
    await notify_admins_new_request(admin_bot, req_id, data.name, data.phone, data.text, "Telegram Mini App")

    return {"status": "success", "request_id": req_id}


@app.get("/api/twa/user-info")
async def twa_get_user_info(user_id: int):
    """
    Повертає інформацію про користувача для Telegram Mini App
    """
    async with SessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user:
            return {"status": "not_found"}

        stats_query = await session.execute(
            select(RequestForm.status, func.count(RequestForm.id))
            .where(RequestForm.user_id == user_id)
            .group_by(RequestForm.status)
        )
        stats = {row[0]: row[1] for row in stats_query.all()}

    from config import ADMIN_IDS
    return {
        "status": "ok",
        "is_admin": user_id in ADMIN_IDS,
        "user": {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone_number,
            "created_at": (user.created_at.isoformat() + "Z") if user.created_at else None
        },
        "stats": {
            "pending": stats.get("pending", 0),
            "in_progress": stats.get("in_progress", 0),
            "completed": stats.get("completed", 0),
            "rejected": stats.get("rejected", 0),
            "total": sum(stats.values())
        }
    }


@app.get("/api/twa/admin/requests")
async def twa_get_admin_requests(admin_id: int, status: Optional[str] = None):
    """
    Повертає список заявок для адміністратора у WebApp з можливістю фільтрації за статусом
    """
    from config import ADMIN_IDS
    if admin_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Access denied")

    async with SessionLocal() as session:
        query = select(RequestForm)
        if status and status != "all":
            query = query.where(RequestForm.status == status)
        query = query.order_by(RequestForm.created_at.desc())
        result = await session.execute(query)
        requests = result.scalars().all()

    return [
        {
            "id": req.id,
            "name": req.name,
            "phone": req.phone,
            "text": req.text,
            "status": req.status,
            "source": req.source,
            "reply_text": req.reply_text,
            "created_at": (req.created_at.isoformat() + "Z") if req.created_at else None
        }
        for req in requests
    ]


@app.get("/api/twa/admin/pending")
async def twa_get_admin_pending(admin_id: int):
    """
    Повертає список очікуючих заявок для панелі адміністратора у WebApp
    """
    from config import ADMIN_IDS
    if admin_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Access denied")

    async with SessionLocal() as session:
        result = await session.execute(
            select(RequestForm)
            .where(RequestForm.status == "pending")
            .order_by(RequestForm.created_at.desc())
        )
        requests = result.scalars().all()

    return [
        {
            "id": req.id,
            "name": req.name,
            "phone": req.phone,
            "text": req.text,
            "status": req.status,
            "source": req.source,
            "reply_text": req.reply_text,
            "created_at": (req.created_at.isoformat() + "Z") if req.created_at else None
        }
        for req in requests
    ]


@app.post("/api/twa/admin/action")
async def twa_admin_action(
    data: TWAAdminActionSchema,
    user_bot: Bot = Depends(get_user_bot),
    admin_bot: Bot = Depends(get_admin_bot)
):
    """
    Обробляє дії адміністратора над заявками з WebApp.
    Відповіді та сповіщення клієнтам відправляються через user_bot.
    """
    from config import ADMIN_IDS
    from database.crud import get_request_form_by_id

    if data.admin_id not in ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Access denied")

    async with SessionLocal() as session:
        req = await get_request_form_by_id(session, data.request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        if data.action == "accept":
            if req.status != "pending":
                raise HTTPException(status_code=400, detail="Заявку вже оброблено іншим адміністратором")
            req.status = "in_progress"
            await session.commit()
            if req.user_id:
                try:
                    await user_bot.send_message(
                        chat_id=req.user_id,
                        text=f"⚙️ *Вашу заявку №{req.id} прийнято в роботу\\!*",
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logging.error(f"Не вдалося надіслати повідомлення користувачу {req.user_id}: {e}")

        elif data.action == "reject":
            if req.status not in ["pending", "in_progress"]:
                raise HTTPException(status_code=400, detail="Заявка вже закрита або відхилена")
            req.status = "rejected"
            await session.commit()
            if req.user_id:
                try:
                    await user_bot.send_message(
                        chat_id=req.user_id,
                        text=f"❌ *Вашу заявку №{req.id} було відхилено спеціалістом\\.*",
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logging.error(f"Не вдалося надіслати повідомлення користувачу {req.user_id}: {e}")

        elif data.action == "reply":
            if not data.reply_text:
                raise HTTPException(status_code=400, detail="Reply text is required")
            if req.status not in ["pending", "in_progress"]:
                raise HTTPException(status_code=400, detail="Заявка вже закрита або відхилена")
            req.status = "completed"
            req.reply_text = data.reply_text
            await session.commit()
            if req.user_id:
                try:
                    from utils.text_utils import escape_markdown
                    reply_message = (
                        f"💬 *Отримано відповідь на вашу заявку №{req.id}*\\:\n\n"
                        f"{escape_markdown(data.reply_text)}"
                    )
                    await user_bot.send_message(
                        chat_id=req.user_id,
                        text=reply_message,
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logging.error(f"Не вдалося надіслати повідомлення користувачу {req.user_id}: {e}")
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

    return {"status": "success"}
