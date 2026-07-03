"""
Обробники адмін-бота: callback-кнопки на заявках, черга, відповіді.
Навігація (/start, /pending, панель) — в admin_start.py
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from states import AdminStates
from database.base import SessionLocal
from database.crud import get_request_form_by_id, update_request_status
from database.models import User, RequestForm
from sqlalchemy import select, func
from utils.text_utils import escape_markdown, format_phone, escape_markdown_code
from config import ADMIN_IDS
import logging
import asyncio
from utils.bot_utils import safe_send_or_edit

router = Router()


def get_admin_home_keyboard() -> ReplyKeyboardMarkup:
    """Reply-клавіатура для адмін-бота (головна панель)"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🏠 Головна панель"))
    return builder.as_markup(resize_keyboard=True)


def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Скасувати відповідь ❌"))
    return builder.as_markup(resize_keyboard=True)


def get_queue_card_data(req: RequestForm) -> tuple[str, InlineKeyboardMarkup]:
    source_name = {
        "bot": "Telegram Bot",
        "site": "Сайт LegalTax",
        "email": "Email Пошта"
    }.get(req.source, req.source)

    safe_text = req.text
    if len(safe_text) > 1500:
        safe_text = safe_text[:1500] + "\n\n... (текст обрізано)"

    status_header = "⚙️ *Заявка в роботі*" if req.status == "in_progress" else "📥 *Нова заявка \\!*"

    admin_text = (
        f"{status_header}\n"
        f"🌐 *Джерело:* `{escape_markdown_code(source_name)}`\n"
        f"⚙️ *ID Заявки:* `#req{req.id}`\n"
        f"───────────────────\n"
        f"👤 *Клієнт:* {escape_markdown(req.name)}\n"
        f"📞 *Телефон:* `{escape_markdown_code(format_phone(req.phone))}`\n"
        f"📝 *Опис проблеми:*\n"
        f"_{escape_markdown(safe_text)}_\n"
        f"───────────────────"
    )

    builder = InlineKeyboardBuilder()
    if req.status == "pending":
        builder.row(
            InlineKeyboardButton(text="В роботу ✅", callback_data=f"adm_work:{req.id}"),
            InlineKeyboardButton(text="Відхилити ❌", callback_data=f"adm_reject:{req.id}")
        )
    else:  # in_progress
        builder.row(
            InlineKeyboardButton(text="Відхилити ❌", callback_data=f"adm_reject:{req.id}")
        )

    builder.row(
        InlineKeyboardButton(text="Відповісти користувачу 💬", callback_data=f"adm_reply:{req.id}")
    )

    if req.status == "in_progress":
        builder.row(
            InlineKeyboardButton(text="Повернути в очікування ⏳", callback_data=f"adm_pending:{req.id}"),
            InlineKeyboardButton(text="Вийти з черги ❌", callback_data="adm_close")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="Залишити в очікуванні ⏳", callback_data=f"adm_pending:{req.id}"),
            InlineKeyboardButton(text="Вийти з черги ❌", callback_data="adm_close")
        )
    return admin_text, builder.as_markup()


async def send_next_queue_card(bot, chat_id, state: FSMContext):
    """Надсилає наступну картку заявки зі стану черги."""
    state_data = await state.get_data()
    seen_ids = state_data.get("seen_ids", [])
    queue_type = state_data.get("queue_type", "pending")

    async with SessionLocal() as session:
        query = select(RequestForm).where(
            RequestForm.status == queue_type
        )
        if seen_ids:
            query = query.where(RequestForm.id.notin_(seen_ids))
        query = query.order_by(RequestForm.created_at.asc()).limit(1)

        result = await session.execute(query)
        req = result.scalar_one_or_none()

    if not req:
        # Заявки закінчилися!
        await state.clear()

        msg = "🎉 *Усі очікуючі заявки оброблені\\! Черга порожня\\.*" if queue_type == "pending" else "🎉 *Немає інших активних заявок у роботі\\.*"
        await safe_send_or_edit(
            bot.send_message,
            chat_id=chat_id,
            text=msg,
            parse_mode="MarkdownV2",
            reply_markup=get_admin_home_keyboard()
        )
        return

    # Додаємо поточну заявку до списку переглянутих
    seen_ids.append(req.id)
    await state.update_data(seen_ids=seen_ids)

    admin_text, reply_markup = get_queue_card_data(req)

    import os
    from aiogram.types import FSInputFile
    photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "legaltax_header.png")
    photo_exists = os.path.exists(photo_path)

    try:
        if photo_exists and len(admin_text) <= 1024:
            try:
                photo = FSInputFile(photo_path)
                await safe_send_or_edit(
                    bot.send_photo,
                    chat_id=chat_id,
                    photo=photo,
                    caption=admin_text,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup
                )
                return
            except Exception as photo_err:
                logging.error(f"Не вдалося надіслати фото черги, пробуємо текстове повідомлення: {photo_err}")

        await safe_send_or_edit(
            bot.send_message,
            chat_id=chat_id,
            text=admin_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Не вдалося надіслати картку черги: {e}")


# === ОБРОБКА CALLBACK-КНОПОК НА ЗАЯВКАХ ===

@router.callback_query(F.data.startswith("adm_work:"))
async def process_admin_work(callback: CallbackQuery, user_bot: Bot):
    """Взяти заявку в роботу. Сповіщення користувачу відправляється через user_bot."""
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await update_request_status(session, req_id, "in_progress")

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено в базі даних", show_alert=True)
        return

    source_name = {
        "bot": "Telegram Bot",
        "site": "Сайт LegalTax",
        "email": "Email Пошта"
    }.get(req.source, req.source)

    new_text = (
        f"📥 *Нова заявка \\!*\n"
        f"🌐 *Джерело:* `{escape_markdown_code(source_name)}`\n"
        f"⚙️ *ID Заявки:* `#req{req_id}`\n"
        f"───────────────────\n"
        f"👤 *Клієнт:* {escape_markdown(req.name)}\n"
        f"📞 *Телефон:* `{escape_markdown_code(format_phone(req.phone))}`\n"
        f"📝 *Опис проблеми:*\n"
        f"_{escape_markdown(req.text)}_\n"
        f"───────────────────\n\n"
        f"🟢 *Статус: Взято в роботу адміном*"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Відповісти користувачу 💬", callback_data=f"adm_reply:{req_id}"))
    builder.row(InlineKeyboardButton(text="Вийти з черги ❌", callback_data="adm_close"))

    try:
        if callback.message.photo:
            await safe_send_or_edit(
                callback.message.edit_caption,
                caption=new_text,
                parse_mode="MarkdownV2",
                reply_markup=builder.as_markup()
            )
        else:
            await safe_send_or_edit(
                callback.message.edit_text,
                text=new_text,
                parse_mode="MarkdownV2",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        logging.error(f"Не вдалося оновити повідомлення адміна: {e}")

    # Сповіщаємо користувача через КЛІЄНТСЬКИЙ бот
    if req.user_id:
        try:
            await safe_send_or_edit(
                user_bot.send_message,
                chat_id=req.user_id,
                text=f"⚙️ *Вашу заявку №{req_id} взято в роботу спеціалістом\\!* Скоро ми зв'яжемося з вами\\.",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Не вдалося надіслати сповіщення користувачу: {e}")

    await safe_send_or_edit(callback.answer, text="Заявку взято в роботу")


@router.callback_query(F.data.startswith("adm_reject:"))
async def process_admin_reject(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await get_request_form_by_id(session, req_id)

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено", show_alert=True)
        return

    source_name = {
        "bot": "Telegram Bot",
        "site": "Сайт LegalTax",
        "email": "Email Пошта"
    }.get(req.source, req.source)

    warning_text = (
        f"⚠️ *Ви впевнені, що хочете відхилити заявку №{req_id}?*\n"
        f"───────────────────\n"
        f"🌐 *Джерело:* `{escape_markdown_code(source_name)}`\n"
        f"👤 *Клієнт:* {escape_markdown(req.name)}\n"
        f"───────────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Так, відхилити ❌", callback_data=f"adm_reject_confirm:{req_id}"),
        InlineKeyboardButton(text="Назад ↩️", callback_data=f"adm_reject_cancel:{req_id}")
    )

    try:
        if callback.message.photo:
            await safe_send_or_edit(
                callback.message.edit_caption,
                caption=warning_text,
                parse_mode="MarkdownV2",
                reply_markup=builder.as_markup()
            )
        else:
            await safe_send_or_edit(
                callback.message.edit_text,
                text=warning_text,
                parse_mode="MarkdownV2",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        logging.error(f"Не вдалося оновити повідомлення для підтвердження відхилення: {e}")

    await safe_send_or_edit(callback.answer)


@router.callback_query(F.data.startswith("adm_reject_confirm:"))
async def process_admin_reject_confirm(callback: CallbackQuery, state: FSMContext, user_bot: Bot):
    """Підтвердження відхилення. Сповіщення користувачу — через user_bot."""
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await update_request_status(session, req_id, "rejected")

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено", show_alert=True)
        return

    source_name = {
        "bot": "Telegram Bot",
        "site": "Сайт LegalTax",
        "email": "Email Пошта"
    }.get(req.source, req.source)

    rejected_text = (
        f"📥 *Нова заявка \\!*\n"
        f"🌐 *Джерело:* `{escape_markdown_code(source_name)}`\n"
        f"⚙️ *ID Заявки:* `#req{req_id}`\n"
        f"───────────────────\n"
        f"👤 *Клієнт:* {escape_markdown(req.name)}\n"
        f"📞 *Телефон:* `{escape_markdown_code(format_phone(req.phone))}`\n"
        f"📝 *Опис проблеми:*\n"
        f"_{escape_markdown(req.text)}_\n"
        f"───────────────────\n\n"
        f"❌ *Статус: Відхилено спеціалістом*"
    )

    try:
        if callback.message.photo:
            await safe_send_or_edit(
                callback.message.edit_caption,
                caption=rejected_text,
                parse_mode="MarkdownV2",
                reply_markup=None
            )
        else:
            await safe_send_or_edit(
                callback.message.edit_text,
                text=rejected_text,
                parse_mode="MarkdownV2",
                reply_markup=None
            )
    except Exception as e:
        logging.error(f"Не вдалося оновити повідомлення: {e}")

    # Сповіщаємо користувача через КЛІЄНТСЬКИЙ бот
    if req.user_id:
        try:
            await safe_send_or_edit(
                user_bot.send_message,
                chat_id=req.user_id,
                text=f"❌ *На жаль, вашу заявку №{req_id} було відхилено спеціалістом\\.*",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Не вдалося надіслати сповіщення користувачу: {e}")

    await safe_send_or_edit(callback.answer, text="Заявку відхилено")

    # Якщо адмін у черзі, показуємо наступну картку після короткої паузи
    state_status = await state.get_state()
    if state_status == AdminStates.in_queue.state:
        await asyncio.sleep(1)
        await send_next_queue_card(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data.startswith("adm_reject_cancel:"))
async def process_admin_reject_cancel(callback: CallbackQuery):
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await get_request_form_by_id(session, req_id)

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено", show_alert=True)
        return

    admin_text, reply_markup = get_queue_card_data(req)

    try:
        if callback.message.photo:
            await safe_send_or_edit(
                callback.message.edit_caption,
                caption=admin_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
        else:
            await safe_send_or_edit(
                callback.message.edit_text,
                text=admin_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Не вдалося відновити оригінальну картку: {e}")

    await safe_send_or_edit(callback.answer)


@router.callback_query(F.data.startswith("adm_pending:"))
async def process_admin_pending(callback: CallbackQuery, state: FSMContext):
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await update_request_status(session, req_id, "pending")

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено", show_alert=True)
        return

    try:
        await safe_send_or_edit(callback.message.delete)
    except Exception as e:
        logging.error(f"Не вдалося видалити повідомлення: {e}")

    await safe_send_or_edit(callback.answer, text="Заявку залишено в очікуванні ⏳")

    state_status = await state.get_state()
    if state_status == AdminStates.in_queue.state:
        await send_next_queue_card(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data == "adm_close")
async def process_admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_send_or_edit(callback.answer, text="Вихід з черги заявок")
    try:
        await safe_send_or_edit(callback.message.delete)
    except Exception as e:
        logging.error(f"Не вдалося видалити повідомлення: {e}")

    await safe_send_or_edit(
        callback.message.answer,
        text="🚪 *Ви вийшли з черги перегляду заявок\\.*",
        parse_mode="MarkdownV2",
        reply_markup=get_admin_home_keyboard()
    )


@router.callback_query(F.data.startswith("adm_reply:"))
async def process_admin_reply_start(callback: CallbackQuery, state: FSMContext):
    req_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        req = await get_request_form_by_id(session, req_id)

    if not req:
        await safe_send_or_edit(callback.answer, text="❌ Заявку не знайдено", show_alert=True)
        return

    current_state = await state.get_state()
    was_in_queue = (current_state == AdminStates.in_queue.state)
    state_data = await state.get_data()
    seen_ids = state_data.get("seen_ids", [])

    await state.update_data(
        reply_to_user_id=req.user_id,
        reply_to_req_id=req_id,
        reply_to_message_id=callback.message.message_id,
        reply_to_chat_id=callback.message.chat.id,
        reply_to_has_photo=bool(callback.message.photo),
        was_in_queue=was_in_queue,
        seen_ids=seen_ids
    )
    await state.set_state(AdminStates.waiting_for_reply_text)

    await safe_send_or_edit(
        callback.message.answer,
        text=f"✍️ *Введіть повідомлення для відповіді клієнту* \\(ID заявки: \\#{req_id}, Клієнт: {escape_markdown(req.name)}\\):\n"
             f"_\\(Для скасування натисиніть кнопку нижче\\)_",
        parse_mode="MarkdownV2",
        reply_markup=get_cancel_reply_keyboard()
    )
    await safe_send_or_edit(callback.answer)


# === НАДСИЛАННЯ ВІДПОВІДІ КЛІЄНТУ ===

@router.message(AdminStates.waiting_for_reply_text, (F.text == "Скасувати відповідь ❌") | (F.text == "/cancel"))
async def cancel_admin_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    was_in_queue = data.get("was_in_queue", False)
    seen_ids = data.get("seen_ids", [])

    await state.clear()

    await safe_send_or_edit(
        message.answer,
        text="Введення відповіді скасовано.",
        reply_markup=get_admin_home_keyboard()
    )

    if was_in_queue:
        await state.set_state(AdminStates.in_queue)
        await state.update_data(seen_ids=seen_ids)
        await send_next_queue_card(message.bot, message.chat.id, state)


@router.message(AdminStates.waiting_for_reply_text)
async def process_admin_reply_send(message: Message, state: FSMContext, user_bot: Bot):
    """Відправка відповіді клієнту. Повідомлення надсилається через КЛІЄНТСЬКИЙ бот."""
    data = await state.get_data()
    await state.clear()

    recipient_user_id = data["reply_to_user_id"]
    req_id = data["reply_to_req_id"]
    reply_to_message_id = data.get("reply_to_message_id")
    reply_to_chat_id = data.get("reply_to_chat_id")
    reply_to_has_photo = data.get("reply_to_has_photo")
    was_in_queue = data.get("was_in_queue", False)
    seen_ids = data.get("seen_ids", [])
    reply_text = message.text.strip()

    # Оновлюємо статус в БД
    async with SessionLocal() as session:
        req = await update_request_status(session, req_id, "completed")

    success = False
    if recipient_user_id:
        try:
            user_msg = (
                f"💬 *Відповідь від спеціаліста LegalTax щодо вашої заявки №{req_id}:*\n"
                f"───────────────────\n"
                f"{escape_markdown(reply_text)}\n"
                f"───────────────────\n"
                f"💡 _Якщо у вас виникли додаткові питання, ви можете створити нову заявку\\._"
            )
            # Відповідь клієнту відправляється через КЛІЄНТСЬКИЙ бот
            await safe_send_or_edit(
                user_bot.send_message,
                chat_id=recipient_user_id,
                text=user_msg,
                parse_mode="MarkdownV2"
            )
            success = True
        except Exception as e:
            logging.error(f"Не вдалося надіслати повідомлення користувачу {recipient_user_id}: {e}")

    if success:
        await safe_send_or_edit(
            message.answer,
            text="✅ Відповідь успішно надіслана користувачу в Telegram та статус заявки оновлено на 'Виконано'!"
        )
    else:
        await safe_send_or_edit(
            message.answer,
            text="⚠️ Користувач не підключений до бота або заблокував його. "
                 "Статус заявки в базі змінено на 'Виконано', але ви повинні відповісти йому особисто по телефону."
        )

    # Оновлюємо оригінальну статус-картку адміна
    if reply_to_message_id and reply_to_chat_id and req:
        source_name = {
            "bot": "Telegram Bot",
            "site": "Сайт LegalTax",
            "email": "Email Пошта"
        }.get(req.source, req.source)

        completed_text = (
            f"📥 *Нова заявка \\!*\n"
            f"🌐 *Джерело:* `{escape_markdown_code(source_name)}`\n"
            f"⚙️ *ID Заявки:* `#req{req_id}`\n"
            f"───────────────────\n"
            f"👤 *Клієнт:* {escape_markdown(req.name)}\n"
            f"📞 *Телефон:* `{escape_markdown_code(format_phone(req.phone))}`\n"
            f"📝 *Опис проблеми:*\n"
            f"_{escape_markdown(req.text)}_\n"
            f"───────────────────\n\n"
            f"✅ *Статус: Виконано / Надіслано відповідь*\n"
            f"💬 _Відповідь: {escape_markdown(reply_text)}_"
        )
        try:
            if reply_to_has_photo:
                await safe_send_or_edit(
                    message.bot.edit_message_caption,
                    chat_id=reply_to_chat_id,
                    message_id=reply_to_message_id,
                    caption=completed_text,
                    parse_mode="MarkdownV2",
                    reply_markup=None
                )
            else:
                await safe_send_or_edit(
                    message.bot.edit_message_text,
                    chat_id=reply_to_chat_id,
                    message_id=reply_to_message_id,
                    text=completed_text,
                    parse_mode="MarkdownV2",
                    reply_markup=None
                )
        except Exception as e:
            logging.error(f"Не вдалося оновити статус-картку адміна при відповіді: {e}")

    # Якщо адмін був у черзі, показуємо наступну картку
    if was_in_queue:
        await state.set_state(AdminStates.in_queue)
        await state.update_data(seen_ids=seen_ids)
        await send_next_queue_card(message.bot, message.chat.id, state)
    else:
        await safe_send_or_edit(
            message.answer,
            text="Повернення до головної панелі",
            reply_markup=get_admin_home_keyboard()
        )
