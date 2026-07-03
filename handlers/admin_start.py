"""
Обробники для адмін-бота: /start, головна панель, перегляд черги заявок.
Цей файл містить точку входу для адмін-бота та навігацію.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from database.base import SessionLocal
from database.models import User, RequestForm
from sqlalchemy import select, func
from config import ADMIN_IDS
from states import AdminStates
from utils.text_utils import escape_markdown
from utils.bot_utils import safe_send_or_edit

router = Router()


@router.message(CommandStart())
async def admin_cmd_start(message: Message, state: FSMContext):
    """Обробник /start для адмін-бота — показує панель адміністратора"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(
            "⛔ Доступ заборонено\\. Цей бот призначений тільки для адміністраторів LegalTax\\.",
            parse_mode="MarkdownV2"
        )
        return

    await state.clear()
    await _show_admin_panel(message)


@router.message(F.text == "🏠 Головна панель")
async def admin_home(message: Message, state: FSMContext):
    """Повернення до головної панелі адміна через reply-кнопку"""
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await _show_admin_panel(message)


async def _show_admin_panel(message: Message):
    """Відображає головну панель адміністратора зі статистикою"""
    async with SessionLocal() as session:
        total_users_query = await session.execute(select(func.count(User.id)))
        total_users = total_users_query.scalar() or 0

        pending_query = await session.execute(
            select(func.count(RequestForm.id)).where(RequestForm.status == "pending")
        )
        pending = pending_query.scalar() or 0

        in_progress_query = await session.execute(
            select(func.count(RequestForm.id)).where(RequestForm.status == "in_progress")
        )
        in_progress = in_progress_query.scalar() or 0

        completed_query = await session.execute(
            select(func.count(RequestForm.id)).where(RequestForm.status == "completed")
        )
        completed = completed_query.scalar() or 0

    admin_info = (
        f"⚙️ *Панель Адміністратора LegalTax*\n"
        f"───────────────────\n"
        f"👥 *Всього користувачів у боті:* `{total_users}`\n\n"
        f"📋 *Статистика заявок \\(загалом\\):*\n"
        f"⏳ Очікують: `{pending}`\n"
        f"⚙️ В роботі: `{in_progress}`\n"
        f"✅ Виконано/Відповіли: `{completed}`\n"
        f"───────────────────\n"
        f"💡 _Усі нові заявки з сайту, пошти та бота надсилаються сюди автоматично з кнопками швидкої відповіді\\._"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Переглянути очікуючі заявки ⏳📋", callback_data="adm_view_pending"))
    builder.row(InlineKeyboardButton(text="Заявки в роботі ⚙️📋", callback_data="adm_view_in_progress"))

    await safe_send_or_edit(
        message.answer,
        text=admin_info,
        parse_mode="MarkdownV2",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "adm_view_pending")
async def process_view_pending_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Переглянути очікуючі заявки'"""
    if callback.from_user.id not in ADMIN_IDS:
        await safe_send_or_edit(callback.answer, text="❌ Доступ заборонено", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.in_queue)
    await state.update_data(seen_ids=[], queue_type="pending")

    async with SessionLocal() as session:
        query = select(RequestForm).where(RequestForm.status == "pending")
        result = await session.execute(query)
        reqs = result.scalars().all()

    if not reqs:
        await state.clear()
        await safe_send_or_edit(callback.answer, text="Усі заявки оброблені! 🎉", show_alert=True)
        return

    from handlers.admin import get_admin_home_keyboard, send_next_queue_card

    await safe_send_or_edit(
        callback.message.answer,
        text="📂 *Запуск черги перегляду заявок\\.\\.\\.*",
        parse_mode="MarkdownV2",
        reply_markup=get_admin_home_keyboard()
    )
    await safe_send_or_edit(callback.answer)
    await send_next_queue_card(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data == "adm_view_in_progress")
async def process_view_in_progress_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Переглянути заявки в роботі'"""
    if callback.from_user.id not in ADMIN_IDS:
        await safe_send_or_edit(callback.answer, text="❌ Доступ заборонено", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.in_queue)
    await state.update_data(seen_ids=[], queue_type="in_progress")

    async with SessionLocal() as session:
        query = select(RequestForm).where(RequestForm.status == "in_progress")
        result = await session.execute(query)
        reqs = result.scalars().all()

    if not reqs:
        await state.clear()
        await safe_send_or_edit(callback.answer, text="Немає активних заявок у роботі! ⚙️", show_alert=True)
        return

    from handlers.admin import get_admin_home_keyboard, send_next_queue_card

    await safe_send_or_edit(
        callback.message.answer,
        text="📂 *Запуск перегляду активних заявок у роботі\\.\\.\\.*",
        parse_mode="MarkdownV2",
        reply_markup=get_admin_home_keyboard()
    )
    await safe_send_or_edit(callback.answer)
    await send_next_queue_card(callback.bot, callback.message.chat.id, state)


@router.message(Command("pending"))
async def list_pending_requests(message: Message, state: FSMContext):
    """Команда /pending — швидкий запуск черги заявок"""
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.clear()
    await state.set_state(AdminStates.in_queue)
    await state.update_data(seen_ids=[], queue_type="pending")

    async with SessionLocal() as session:
        query = select(RequestForm).where(RequestForm.status == "pending")
        result = await session.execute(query)
        reqs = result.scalars().all()

    if not reqs:
        await state.clear()
        await safe_send_or_edit(
            message.answer,
            text="🎉 *Усі очікуючі заявки оброблені\\! Черга порожня\\.*",
            parse_mode="MarkdownV2"
        )
        return

    from handlers.admin import get_admin_home_keyboard, send_next_queue_card

    await safe_send_or_edit(
        message.answer,
        text="📂 *Запуск черги перегляду заявок\\.\\.\\.*",
        parse_mode="MarkdownV2",
        reply_markup=get_admin_home_keyboard()
    )
    await send_next_queue_card(message.bot, message.chat.id, state)
