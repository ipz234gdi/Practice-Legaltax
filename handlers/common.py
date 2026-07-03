from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from database.base import SessionLocal
from database.crud import get_or_create_user
from utils.text_utils import escape_markdown
from config import WEB_HOST, WEB_PORT

router = Router()

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Головне меню клієнтського бота (без адмін-кнопок)"""
    import config as _cfg
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Особистий кабінет 👤"),
        KeyboardButton(text="Залишити заявку 📝")
    )
    builder.row(
        KeyboardButton(text="Калькулятор податків 📊"),
        KeyboardButton(text="Про LegalTax ℹ️")
    )
    builder.row(
        KeyboardButton(text="🚀 Відкрити LegalTax App", web_app=WebAppInfo(url=_cfg.TWA_URL))
    )
    return builder.as_markup(resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Очищуємо попередній стан FSM, якщо він був
    await state.clear()
    
    # Реєструємо користувача в базі даних
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    async with SessionLocal() as session:
        await get_or_create_user(session, user_id, username, first_name, last_name)
    
    greeting = (
        f"💼 *LegalTax \\| Юридично\\-бухгалтерська допомога*\n\n"
        f"Вітаємо, {escape_markdown(first_name or 'користувач')}\\!\n\n"
        f"Цей бот допоможе вам оперативно зв'язатися з нашими юристами та бухгалтерами, "
        f"розрахувати податки, отримати код авторизації для сайту та переглянути ваші поточні заявки\\.\n\n"
        f"Оберіть потрібну дію в меню нижче 👇"
    )
    
    await message.answer(
        text=greeting,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard()
    )
    
    # Відправляємо inline-кнопку для запуску Mini App
    import config as _cfg
    webapp_url = _cfg.TWA_URL
    webapp_builder = InlineKeyboardBuilder()
    webapp_builder.row(
        InlineKeyboardButton(
            text="🚀 Відкрити LegalTax App",
            web_app=WebAppInfo(url=webapp_url)
        )
    )
    await message.answer(
        text="🌐 *Спробуйте наш новий Mini App\\!*\n_Сучасний інтерфейс для зручної роботи з LegalTax_",
        parse_mode="MarkdownV2",
        reply_markup=webapp_builder.as_markup()
    )

@router.message(F.text == "Про LegalTax ℹ️")
@router.message(Command("help"))
async def cmd_about(message: Message):
    about_text = (
        "🏢 *Компанія LegalTax*\n\n"
        "Ми надаємо професійні послуги з:\n"
        "• Реєстрації та закриття ФОП/ТОВ\n"
        "• Ведення бухгалтерського обліку\n"
        "• Подання податкової звітності\n"
        "• Юридичного супроводу бізнесу\n\n"
        "🌐 *Наш сайт:* [legaltax\\.com\\.ua](https://legaltax.com.ua)\n"
        "📧 *Пошта:* `reiclid@gmail.com`\n\n"
        "💡 _Використовуйте кнопки головного меню для роботи з ботом\\._"
    )
    
    await message.answer(
        text=about_text,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )
