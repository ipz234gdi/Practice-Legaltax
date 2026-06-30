from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from states import UserForm
from database.base import SessionLocal
from database.crud import get_user_by_id, create_request_form
from utils.text_utils import escape_markdown, format_phone, escape_markdown_code
from config import ADMIN_IDS
from aiogram import Bot
import os
import logging
from utils.bot_utils import safe_send_or_edit

router = Router()

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Скасувати подачу ❌"))
    return builder.as_markup(resize_keyboard=True)

@router.message(F.text == "Скасувати подачу ❌")
async def cancel_form(message: Message, state: FSMContext):
    await state.clear()
    from handlers.common import get_main_menu_keyboard
    await message.answer(
        text="Подання заявки скасовано. Повернення до головного меню.",
        reply_markup=get_main_menu_keyboard()
    )

@router.message(F.text == "Залишити заявку 📝")
async def start_form(message: Message, state: FSMContext):
    user_id = message.from_user.id

    async with SessionLocal() as session:
        user = await get_user_by_id(session, user_id)

    await state.set_state(UserForm.waiting_for_name)

    # Спробуємо підставити ім'я з тг
    default_name = message.from_user.first_name or ""
    prompt = (
        f"📝 *Створення заявки*\n\n"
        f"Будь ласка, вкажіть ваше ім'я або назву компанії\\.\n"
        f"💡 _\\(Ви можете ввести вручну або відправити поточне ім'я з Telegram: `{escape_markdown_code(default_name)}`\\)_"
    )

    builder = ReplyKeyboardBuilder()
    if default_name:
        builder.row(KeyboardButton(text=default_name))
    builder.row(KeyboardButton(text="Скасувати подачу ❌"))

    await message.answer(
        text=prompt,
        parse_mode="MarkdownV2",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(UserForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if name == "Скасувати подачу ❌":
        return

    await state.update_data(name=name)
    await state.set_state(UserForm.waiting_for_phone)

    user_id = message.from_user.id
    async with SessionLocal() as session:
        user = await get_user_by_id(session, user_id)

    builder = ReplyKeyboardBuilder()

    # Перевіримо, чи є збережений телефон
    if user and user.phone_number:
        builder.row(KeyboardButton(text=user.phone_number))
        prompt = (
            f"👤 *Ім'я:* `{escape_markdown_code(name)}` збережено\\.\n\n"
            f"Тепер вкажіть ваш контактний номер телефону\\.\n"
            f"💡 _\\(Ви можете натиснути на кнопку з вашим номером `{escape_markdown_code(user.phone_number)}` або ввести інший номер вручну\\)_"
        )
    else:
        builder.row(KeyboardButton(text="Поділитися номером 📱", request_contact=True))
        prompt = (
            f"👤 *Ім'я:* `{escape_markdown_code(name)}` збережено\\.\n\n"
            f"Вкажіть ваш контактний номер телефону 👇"
        )

    builder.row(KeyboardButton(text="Скасувати подачу ❌"))

    await message.answer(
        text=prompt,
        parse_mode="MarkdownV2",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(UserForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.text == "Скасувати подачу ❌":
        return

    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()
        # Проста перевірка на наявність цифр
        digits = "".join(filter(str.isdigit, phone))
        if len(digits) < 9:
            await message.answer(
                text="⚠️ Некоректний формат номеру\\. Будь ласка, введіть дійсний номер телефону\\."
            )
            return

    if not phone.startswith("+") and phone.isdigit():
        phone = "+" + phone

    await state.update_data(phone=phone)
    await state.set_state(UserForm.waiting_for_text)

    await message.answer(
        text=f"📞 *Телефон:* `{escape_markdown_code(format_phone(phone))}` збережено\\.\n\n"
             f"Будь ласка, детально опишіть ваше питання або необхідну послугу:",
        parse_mode="MarkdownV2",
        reply_markup=get_cancel_keyboard()
    )

@router.message(UserForm.waiting_for_text)
async def process_text(message: Message, state: FSMContext, admin_bot: Bot):
    """Обробка тексту заявки. admin_bot передається через dispatcher kwargs."""
    text = message.text.strip()
    if text == "Скасувати подачу ❌":
        return

    user_data = await state.get_data()
    await state.clear()

    user_id = message.from_user.id
    name = user_data["name"]
    phone = user_data["phone"]

    # Зберігаємо в БД
    async with SessionLocal() as session:
        req = await create_request_form(
            session=session,
            name=name,
            phone=phone,
            text=text,
            user_id=user_id,
            source="bot"
        )
        req_id = req.id

    # Повертаємо головне меню
    from handlers.common import get_main_menu_keyboard

    await message.answer(
        text=f"✅ *Вашу заявку №{req_id} успішно прийнято\\!*\n\n"
             f"Наші спеціалісти розглянуть її найближчим часом та зв'яжуться з вами за номером `{escape_markdown_code(format_phone(phone))}`\\.",
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )

    # Сповіщаємо адмінів через адмін-бота
    await notify_admins_new_request(admin_bot, req_id, name, phone, text, "Telegram Bot")

async def notify_admins_new_request(bot: Bot, req_id: int, name: str, phone: str, text: str, source: str):
    """
    Надсилає повідомлення про нову заявку всім адмінам з кнопками дій.
    bot — має бути адмін-бот для відправки сповіщень.
    """
    safe_text = text
    if len(safe_text) > 1500:
        safe_text = safe_text[:1500] + "\n\n... (текст обрізано)"

    admin_text = (
        f"📥 *Нова заявка \\!*\n"
        f"🌐 *Джерело:* `{escape_markdown_code(source)}`\n"
        f"⚙️ *ID Заявки:* `#req{req_id}`\n"
        f"───────────────────\n"
        f"👤 *Клієнт:* {escape_markdown(name)}\n"
        f"📞 *Телефон:* `{escape_markdown_code(format_phone(phone))}`\n"
        f"📝 *Опис проблеми:*\n"
        f"_{escape_markdown(safe_text)}_\n"
        f"───────────────────"
    )

    # Робимо inline-клавіатуру дій
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="В роботу ✅", callback_data=f"adm_work:{req_id}"),
        InlineKeyboardButton(text="Відхилити ❌", callback_data=f"adm_reject:{req_id}")
    )
    builder.row(
        InlineKeyboardButton(text="Відповісти користувачу 💬", callback_data=f"adm_reply:{req_id}")
    )
    builder.row(
        InlineKeyboardButton(text="Залишити в очікуванні ⏳", callback_data=f"adm_pending:{req_id}"),
        InlineKeyboardButton(text="Вийти з черги ❌", callback_data="adm_close")
    )

    # Визначаємо шлях до картинки-заставки
    photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "legaltax_header.png")
    photo_exists = os.path.exists(photo_path)

    for admin_id in ADMIN_IDS:
        try:
            if photo_exists and len(admin_text) <= 1024:
                try:
                    photo = FSInputFile(photo_path)
                    await safe_send_or_edit(
                        bot.send_photo,
                        chat_id=admin_id,
                        photo=photo,
                        caption=admin_text,
                        parse_mode="MarkdownV2",
                        reply_markup=builder.as_markup()
                    )
                    continue
                except Exception as photo_err:
                    logging.error(f"Не вдалося надіслати фото сповіщення адміну {admin_id}, пробуємо текст: {photo_err}")
            await safe_send_or_edit(
                bot.send_message,
                chat_id=admin_id,
                text=admin_text,
                parse_mode="MarkdownV2",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logging.error(f"Не вдалося надіслати сповіщення адміну {admin_id}: {e}")
