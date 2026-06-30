from aiogram import Router, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from database.base import SessionLocal
from database.crud import get_user_by_id, get_or_create_user, update_user_phone, get_user_requests
from utils.text_utils import escape_markdown, format_phone, escape_markdown_code
from datetime import datetime
from states import CabinetStates

router = Router()

def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Надіслати номер телефону 📱", request_contact=True))
    builder.row(KeyboardButton(text="Скасувати ❌"))
    return builder.as_markup(resize_keyboard=True)

@router.message(F.text == "Особистий кабінет 👤")
async def show_cabinet(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    async with SessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user:
            user = await get_or_create_user(
                session=session,
                user_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        
        if not user or not user.phone_number:
            prompt = (
                f"👤 *Особистий кабінет*\n\n"
                f"Для доступу до особистого кабінету необхідно підтвердити ваш номер телефону\\.\n"
                f"Будь ласка, натисніть кнопку нижче, щоб поділитися контактом, або введіть номер вручну \\(наприклад: \\+380991234567\\) 👇"
            )
            await state.set_state(CabinetStates.waiting_for_phone)
            await message.answer(
                text=prompt,
                parse_mode="MarkdownV2",
                reply_markup=get_phone_request_keyboard()
            )
            return

        # Отримуємо статистику та останні заявки користувача
        from database.models import RequestForm
        from sqlalchemy import select, func
        
        stats_query = await session.execute(
            select(RequestForm.status, func.count(RequestForm.id))
            .where(RequestForm.user_id == user_id)
            .group_by(RequestForm.status)
        )
        stats = {row[0]: row[1] for row in stats_query.all()}
        total_count = sum(stats.values())
        
        requests = await get_user_requests(session, user_id, limit=5)
        
        status_emojis = {
            "pending": "⏳ Очікує",
            "in_progress": "⚙️ В роботі",
            "completed": "✅ Виконано",
            "rejected": "❌ Відхилено"
        }
        
        requests_text = ""
        if requests:
            for req in requests:
                status_ukr = status_emojis.get(req.status, req.status)
                date_str = escape_markdown(req.created_at.strftime("%d.%m.%Y %H:%M"))
                short_text = req.text[:50] + "..." if len(req.text) > 50 else req.text
                requests_text += (
                    f"• *Заявка №{req.id}* \\({date_str}\\)\n"
                    f"  Статус: {escape_markdown(status_ukr)}\n"
                    f"  Суть: _{escape_markdown(short_text)}_\n\n"
                )
        else:
            requests_text = "_У вас поки немає поданих заявок\\._\n"
            
        stats_text = (
            f"📊 *Всього заявок:* {total_count} \\("
            f"Очікують: {stats.get('pending', 0)} \\| "
            f"В роботі: {stats.get('in_progress', 0)} \\| "
            f"Виконано: {stats.get('completed', 0)} \\| "
            f"Відхилено: {stats.get('rejected', 0)}\\)"
        )
        
        cabinet_info = (
            f"👤 *Особистий кабінет клієнта*\n"
            f"───────────────────\n"
            f"📱 *Ваш телефон:* `{escape_markdown_code(format_phone(user.phone_number))}`\n"
            f"📅 *Дата реєстрації:* {escape_markdown(user.created_at.strftime('%d.%m.%Y'))}\n"
            f"{stats_text}\n"
            f"───────────────────\n"
            f"📋 *Ваші останні заявки:* \n"
            f"{requests_text}"
            f"───────────────────\n"
            f"💡 _Якщо ви хочете подати нову заявку, скористайтеся відповідною кнопкою в головному меню\\._"
        )
        
        builder = InlineKeyboardBuilder()
        if total_count > 0:
            builder.row(InlineKeyboardButton(text="📋 Переглянути всі заявки", callback_data="cab_reqs:0"))
            
        await message.answer(
            text=cabinet_info,
            parse_mode="MarkdownV2",
            reply_markup=builder.as_markup()
        )

@router.message(CabinetStates.waiting_for_phone, F.contact)
@router.message(CabinetStates.waiting_for_phone, F.text)
async def process_cabinet_phone(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text == "Скасувати ❌":
        await state.clear()
        from handlers.common import get_main_menu_keyboard
        from config import ADMIN_IDS
        is_admin = user_id in ADMIN_IDS
        await message.answer(
            text="Дію скасовано. Повернення до головного меню.",
            reply_markup=get_main_menu_keyboard(is_admin)
        )
        return
        
    phone = ""
    if message.contact:
        if message.contact.user_id != user_id:
            await message.answer(
                text="⚠️ Будь ласка, надішліть саме *свій* контакт за допомогою кнопки\\.",
                parse_mode="MarkdownV2"
            )
            return
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        # Проста перевірка на наявність цифр
        digits = "".join(filter(str.isdigit, phone))
        if len(digits) < 9:
            await message.answer(
                text="⚠️ Некоректний формат номеру\\. Будь ласка, введіть дійсний номер телефону\\.",
                parse_mode="MarkdownV2"
            )
            return

    if not phone.startswith("+") and phone.isdigit():
        phone = "+" + phone
        
    async with SessionLocal() as session:
        await update_user_phone(
            session=session,
            user_id=user_id,
            phone_number=phone,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
    await state.clear()
    
    await message.answer(
        text="✅ Номер телефону успішно підтверджено та збережено\\!",
        parse_mode="MarkdownV2"
    )
    
    # Показуємо оновлений кабінет
    await show_cabinet(message, state)

@router.message(F.text == "Скасувати ❌")
async def cancel_contact_auth(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    from handlers.common import get_main_menu_keyboard
    from config import ADMIN_IDS
    is_admin = user_id in ADMIN_IDS
    
    await message.answer(
        text="Дію скасовано. Повернення до головного меню.",
        reply_markup=get_main_menu_keyboard(is_admin)
    )

@router.callback_query(F.data.startswith("cab_reqs:"))
async def paginate_user_requests(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    limit = 5
    offset = page * limit
    
    async with SessionLocal() as session:
        # Get total count
        from database.models import RequestForm
        from sqlalchemy import select, func
        count_query = await session.execute(
            select(func.count(RequestForm.id)).where(RequestForm.user_id == user_id)
        )
        total_count = count_query.scalar_one_or_none() or 0
        
        # Get page requests
        result = await session.execute(
            select(RequestForm)
            .where(RequestForm.user_id == user_id)
            .order_by(RequestForm.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        requests = result.scalars().all()
        
    if not requests:
        await callback.answer("У вас немає заявок на цій сторінці.")
        return
        
    status_emojis = {
        "pending": "⏳ Очікує",
        "in_progress": "⚙️ В роботі",
        "completed": "✅ Виконано",
        "rejected": "❌ Відхилено"
    }
    
    total_pages = (total_count + limit - 1) // limit
    text = f"📋 *Всі ваші заявки \\(Сторінка {page + 1} з {total_pages}\\)*\\:\n\n"
    
    for req in requests:
        status_ukr = status_emojis.get(req.status, req.status)
        date_str = escape_markdown(req.created_at.strftime("%d.%m.%Y %H:%M"))
        short_text = req.text[:100] + "..." if len(req.text) > 100 else req.text
        text += (
            f"• *Заявка №{req.id}* \\({date_str}\\)\n"
            f"  Статус: {escape_markdown(status_ukr)}\n"
            f"  Суть: _{escape_markdown(short_text)}_\n\n"
        )
        
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"cab_reqs:{page - 1}"))
    if (page + 1) * limit < total_count:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"cab_reqs:{page + 1}"))
        
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="👤 Особистий кабінет", callback_data="cab_refresh"))
    
    await callback.message.edit_text(
        text=text,
        parse_mode="MarkdownV2",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "cab_refresh")
async def refresh_cabinet_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    async with SessionLocal() as session:
        user = await get_user_by_id(session, user_id)
        if not user or not user.phone_number:
            await callback.answer("Спочатку підтвердіть номер телефону в меню.")
            return
            
        from database.models import RequestForm
        from sqlalchemy import select, func
        stats_query = await session.execute(
            select(RequestForm.status, func.count(RequestForm.id))
            .where(RequestForm.user_id == user_id)
            .group_by(RequestForm.status)
        )
        stats = {row[0]: row[1] for row in stats_query.all()}
        total_count = sum(stats.values())
        
        requests = await get_user_requests(session, user_id, limit=5)
        
    status_emojis = {
        "pending": "⏳ Очікує",
        "in_progress": "⚙️ В роботі",
        "completed": "✅ Виконано",
        "rejected": "❌ Відхилено"
    }
    
    requests_text = ""
    if requests:
        for req in requests:
            status_ukr = status_emojis.get(req.status, req.status)
            date_str = escape_markdown(req.created_at.strftime("%d.%m.%Y %H:%M"))
            short_text = req.text[:50] + "..." if len(req.text) > 50 else req.text
            requests_text += (
                f"• *Заявка №{req.id}* \\({date_str}\\)\n"
                f"  Статус: {escape_markdown(status_ukr)}\n"
                f"  Суть: _{escape_markdown(short_text)}_\n\n"
            )
    else:
        requests_text = "_У вас поки немає поданих заявок\\._\n"
        
    stats_text = (
        f"📊 *Всього заявок:* {total_count} \\("
        f"Очікують: {stats.get('pending', 0)} \\| "
        f"В роботі: {stats.get('in_progress', 0)} \\| "
        f"Виконано: {stats.get('completed', 0)} \\| "
        f"Відхилено: {stats.get('rejected', 0)}\\)"
    )
    
    cabinet_info = (
        f"👤 *Особистий кабінет клієнта*\n"
        f"───────────────────\n"
        f"📱 *Ваш телефон:* `{escape_markdown_code(format_phone(user.phone_number))}`\n"
        f"📅 *Дата реєстрації:* {escape_markdown(user.created_at.strftime('%d.%m.%Y'))}\n"
        f"{stats_text}\n"
        f"───────────────────\n"
        f"📋 *Ваші останні заявки:* \n"
        f"{requests_text}"
        f"───────────────────\n"
        f"💡 _Якщо ви хочете подати нову заявку, скористайтеся відповідною кнопкою в головному меню\\._"
    )
    
    builder = InlineKeyboardBuilder()
    if total_count > 0:
        builder.row(InlineKeyboardButton(text="📋 Переглянути всі заявки", callback_data="cab_reqs:0"))
        
    await callback.message.edit_text(
        text=cabinet_info,
        parse_mode="MarkdownV2",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
