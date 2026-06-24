from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from states import CalculatorStates
from utils.text_utils import escape_markdown

router = Router()

def get_calculator_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="ФОП 1 Група", callback_data="calc_g:1"),
        InlineKeyboardButton(text="ФОП 2 Група", callback_data="calc_g:2")
    )
    builder.row(
        InlineKeyboardButton(text="ФОП 3 Група (5% без ПДВ)", callback_data="calc_g:3_5"),
        InlineKeyboardButton(text="ФОП 3 Група (3% + ПДВ)", callback_data="calc_g:3_3")
    )
    return builder.as_markup()

@router.message(F.text == "Калькулятор податків 📊")
async def show_calculator(message: Message, state: FSMContext):
    await state.clear()
    
    prompt = (
        f"📊 *Калькулятор податків для ФОП \\(Україна\\)*\n\n"
        f"Цей калькулятор допоможе вам приблизно розрахувати податкове навантаження на поточний рік\\.\n\n"
        f"Оберіть вашу групу оподаткування 👇"
    )
    await message.answer(
        text=prompt,
        parse_mode="MarkdownV2",
        reply_markup=get_calculator_menu()
    )

@router.callback_query(F.data.startswith("calc_g:"))
async def process_calc_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split(":")[1]
    
    # 2026/2024 approximation of Ukrainian Tax Rates
    # ЄСВ (22% від мінімальної заробітної плати - наразі мін. зарплата ~8000 грн, отже ЄСВ = 1760 грн/місяць або 5280 грн/квартал)
    # Єдиний податок (Група 1: до 10% прожиткового мінімуму ~302.80 грн/міс)
    # Єдиний податок (Група 2: до 20% мін. зарплати ~1600 грн/міс)
    
    esv_monthly = 1760.0
    esv_quarterly = esv_monthly * 3
    
    if group == "1":
        single_tax = 302.80
        limit = 1185700
        result_text = (
            f"📊 *Розрахунок податків: ФОП 1 Група*\n"
            f"───────────────────\n"
            f"💵 *Єдиний податок:* `{single_tax:.2f} грн/місяць`\n"
            f"🛡️ *ЄСВ:* `{esv_monthly:.2f} грн/місяць` \\(`{esv_quarterly:.2f} грн/квартал`\\)\n"
            f"📈 *Ліміт доходу на рік:* `{limit:,} грн`\n"
            f"───────────────────\n"
            f"ℹ️ _Підходить для роздрібної торгівлі на ринках або надання побутових послуг населенню\\._"
        ).replace(",", " ")
        
        await callback.message.edit_text(
            text=result_text,
            parse_mode="MarkdownV2",
            reply_markup=get_calculator_menu()
        )
        await callback.answer()
        
    elif group == "2":
        single_tax = 1600.0
        limit = 5921400
        result_text = (
            f"📊 *Розрахунок податків: ФОП 2 Група*\n"
            f"───────────────────\n"
            f"💵 *Єдиний податок (макс\\.):* `{single_tax:.2f} грн/місяць`\n"
            f"🛡️ *ЄСВ:* `{esv_monthly:.2f} грн/місяць` \\(`{esv_quarterly:.2f} грн/квартал`\\)\n"
            f"📈 *Ліміт доходу на рік:* `{limit:,} грн`\n"
            f"───────────────────\n"
            f"ℹ️ _Підходить для послуг населенню та платникам єдиного податку, виробництва товарів, ресторанного бізнесу\\._"
        ).replace(",", " ")
        
        await callback.message.edit_text(
            text=result_text,
            parse_mode="MarkdownV2",
            reply_markup=get_calculator_menu()
        )
        await callback.answer()
        
    elif group in ["3_5", "3_3"]:
        rate = 0.05 if group == "3_5" else 0.03
        rate_percent = "5%" if group == "3_5" else "3% (+ ПДВ)"
        
        await state.update_data(rate=rate, rate_percent=rate_percent)
        await state.set_state(CalculatorStates.waiting_for_revenue)
        
        await callback.message.answer(
            text="💰 Введіть суму вашого очікуваного доходу (в грн) за квартал або рік:\n"
                 "_(просто введіть число, наприклад: 150000)_"
        )
        await callback.answer()

@router.message(CalculatorStates.waiting_for_revenue)
async def process_revenue(message: Message, state: FSMContext):
    revenue_text = message.text.strip().replace(" ", "").replace(",", ".")
    
    try:
        revenue = float(revenue_text)
        if revenue < 0:
            raise ValueError()
    except ValueError:
        await message.answer(
            text="⚠️ Будь ласка, введіть коректне додатне число (наприклад, 125000 або 75300.50):"
        )
        return
        
    data = await state.get_data()
    rate = data["rate"]
    rate_percent = data["rate_percent"]
    await state.clear()
    
    single_tax = revenue * rate
    esv_monthly = 1760.0
    esv_quarterly = esv_monthly * 3
    total_tax = single_tax + esv_quarterly
    limit = 8285400
    
    rate_percent_esc = escape_markdown(rate_percent)
    
    result_text = (
        f"📊 *Розрахунок податків: ФОП 3 Група ({rate_percent_esc})*\n"
        f"───────────────────\n"
        f"💵 *Ваш дохід:* `{revenue:,.2f} грн`\n"
        f"📈 *Ставка Єдиного податку:* `{rate_percent_esc}`\n"
        f"💰 *Сума Єдиного податку:* `{single_tax:,.2f} грн`\n"
        f"🛡️ *ЄСВ (за 1 квартал):* `{esv_quarterly:,.2f} грн`\n"
        f"───────────────────\n"
        f"🧾 *Загальні податки за квартал:* `{total_tax:,.2f} грн`\n"
        f"📊 *Чистий дохід:* `{(revenue - total_tax):,.2f} грн`\n"
        f"📈 *Річний ліміт доходу:* `{limit:,.2f} грн`\n"
        f"───────────────────\n"
        f"💡 _Податок 3 групи сплачується щоквартально протягом 40 днів після закінчення кварталу\\._"
    ).replace(",", " ") # Замінюємо англійські коми на пробіли для гарного розділення розрядів
    
    from handlers.common import get_main_menu_keyboard
    from config import ADMIN_IDS
    is_admin = message.from_user.id in ADMIN_IDS
    
    await message.answer(
        text=result_text,
        parse_mode="MarkdownV2",
        reply_markup=get_main_menu_keyboard(is_admin)
    )
