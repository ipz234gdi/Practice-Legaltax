from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from states import CalculatorStates

router = Router()

# ═══════════════════════════════════════════════════════════
# Актуальні ставки 2026 року (Україна)
# ═══════════════════════════════════════════════════════════
MIN_SALARY = 8647.0          # Мінімальна заробітна плата (грн)
MIN_LIVING = 3328.0          # Прожитковий мінімум для працездатних (грн)

ESV_RATE = 0.22              # Ставка ЄСВ
ESV_MONTHLY = MIN_SALARY * ESV_RATE   # 1 902.34 грн/місяць
ESV_QUARTERLY = ESV_MONTHLY * 3       # 5 707.02 грн/квартал
ESV_YEARLY = ESV_MONTHLY * 12         # 22 828.08 грн/рік

# Єдиний податок (ЄП)
EP_GROUP1 = MIN_LIVING * 0.10   # 332.80 грн/міс (10% прожит.мін.)
EP_GROUP2 = MIN_SALARY * 0.20   # 1 729.40 грн/міс (20% мінзарплати)

# Військовий збір (ВЗ) — фіксований для 1-2 групи
VZ_FIXED = MIN_SALARY * 0.10    # 864.70 грн/міс (10% мінзарплати)
VZ_GROUP3_RATE = 0.01            # 1% від доходу для 3 групи

# Ліміти доходу на рік
LIMIT_GROUP1 = 1_444_049
LIMIT_GROUP2 = 7_211_598
LIMIT_GROUP3 = 10_091_049
# ═══════════════════════════════════════════════════════════


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


def fmt(value: float) -> str:
    """Форматує число з пробілами як розділювачами розрядів (123 456.78)"""
    if value == int(value):
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ")


@router.message(F.text == "Калькулятор податків 📊")
async def show_calculator(message: Message, state: FSMContext):
    await state.clear()

    prompt = (
        "📊 <b>Калькулятор податків для ФОП (Україна, 2026)</b>\n\n"
        "Цей калькулятор допоможе вам приблизно розрахувати податкове навантаження.\n\n"
        f"📌 <i>Мін. зарплата: {fmt(MIN_SALARY)} грн | "
        f"Прожит. мінімум: {fmt(MIN_LIVING)} грн</i>\n\n"
        "Оберіть вашу групу оподаткування 👇"
    )
    await message.answer(
        text=prompt,
        parse_mode="HTML",
        reply_markup=get_calculator_menu()
    )


@router.callback_query(F.data.startswith("calc_g:"))
async def process_calc_group(callback: CallbackQuery, state: FSMContext):
    group = callback.data.split(":")[1]

    if group == "1":
        monthly_total = EP_GROUP1 + VZ_FIXED + ESV_MONTHLY
        quarterly_total = monthly_total * 3
        yearly_total = monthly_total * 12

        result_text = (
            "📊 <b>ФОП 1 Група — Розрахунок податків (2026)</b>\n"
            "───────────────────\n"
            f"💵 <b>Єдиний податок:</b> <code>{fmt(EP_GROUP1)} грн/міс</code>\n"
            f"🪖 <b>Військовий збір:</b> <code>{fmt(VZ_FIXED)} грн/міс</code>\n"
            f"🛡️ <b>ЄСВ:</b> <code>{fmt(ESV_MONTHLY)} грн/міс</code>\n"
            "───────────────────\n"
            f"🧾 <b>Загалом на місяць:</b> <code>{fmt(monthly_total)} грн</code>\n"
            f"🧾 <b>Загалом на квартал:</b> <code>{fmt(quarterly_total)} грн</code>\n"
            f"🧾 <b>Загалом на рік:</b> <code>{fmt(yearly_total)} грн</code>\n"
            f"📈 <b>Ліміт доходу на рік:</b> <code>{fmt(LIMIT_GROUP1)} грн</code>\n"
            "───────────────────\n"
            "ℹ️ <i>Підходить для роздрібної торгівлі на ринках або надання побутових послуг населенню.</i>"
        )

        await callback.message.edit_text(
            text=result_text,
            parse_mode="HTML",
            reply_markup=get_calculator_menu()
        )
        await callback.answer()

    elif group == "2":
        monthly_total = EP_GROUP2 + VZ_FIXED + ESV_MONTHLY
        quarterly_total = monthly_total * 3
        yearly_total = monthly_total * 12

        result_text = (
            "📊 <b>ФОП 2 Група — Розрахунок податків (2026)</b>\n"
            "───────────────────\n"
            f"💵 <b>Єдиний податок (макс.):</b> <code>{fmt(EP_GROUP2)} грн/міс</code>\n"
            f"🪖 <b>Військовий збір:</b> <code>{fmt(VZ_FIXED)} грн/міс</code>\n"
            f"🛡️ <b>ЄСВ:</b> <code>{fmt(ESV_MONTHLY)} грн/міс</code>\n"
            "───────────────────\n"
            f"🧾 <b>Загалом на місяць:</b> <code>{fmt(monthly_total)} грн</code>\n"
            f"🧾 <b>Загалом на квартал:</b> <code>{fmt(quarterly_total)} грн</code>\n"
            f"🧾 <b>Загалом на рік:</b> <code>{fmt(yearly_total)} грн</code>\n"
            f"📈 <b>Ліміт доходу на рік:</b> <code>{fmt(LIMIT_GROUP2)} грн</code>\n"
            "───────────────────\n"
            "ℹ️ <i>Підходить для послуг населенню та платникам єдиного податку, виробництва товарів, ресторанного бізнесу.</i>"
        )

        await callback.message.edit_text(
            text=result_text,
            parse_mode="HTML",
            reply_markup=get_calculator_menu()
        )
        await callback.answer()

    elif group in ["3_5", "3_3"]:
        rate = 0.05 if group == "3_5" else 0.03
        rate_percent = "5%" if group == "3_5" else "3% (+ ПДВ)"

        await state.update_data(rate=rate, rate_percent=rate_percent)
        await state.set_state(CalculatorStates.waiting_for_revenue)

        await callback.message.answer(
            text=(
                "💰 Введіть суму вашого очікуваного доходу (в грн) за квартал або рік:\n"
                "<i>(просто введіть число, наприклад: 150000)</i>"
            ),
            parse_mode="HTML"
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

    # Розрахунок
    single_tax = revenue * rate
    military_levy = revenue * VZ_GROUP3_RATE
    total_tax = single_tax + military_levy + ESV_QUARTERLY
    net_income = revenue - total_tax

    result_text = (
        f"📊 <b>ФОП 3 Група ({rate_percent}) — Розрахунок (2026)</b>\n"
        "───────────────────\n"
        f"💵 <b>Ваш дохід:</b> <code>{fmt(revenue)} грн</code>\n"
        f"📈 <b>Ставка ЄП:</b> <code>{rate_percent}</code>\n"
        f"💰 <b>Єдиний податок:</b> <code>{fmt(single_tax)} грн</code>\n"
        f"🪖 <b>Військовий збір (1%):</b> <code>{fmt(military_levy)} грн</code>\n"
        f"🛡️ <b>ЄСВ (за 1 квартал):</b> <code>{fmt(ESV_QUARTERLY)} грн</code>\n"
        "───────────────────\n"
        f"🧾 <b>Загальні податки за квартал:</b> <code>{fmt(total_tax)} грн</code>\n"
        f"📊 <b>Чистий дохід:</b> <code>{fmt(net_income)} грн</code>\n"
        f"📈 <b>Річний ліміт доходу:</b> <code>{fmt(LIMIT_GROUP3)} грн</code>\n"
        "───────────────────\n"
        "💡 <i>Податок 3 групи сплачується щоквартально протягом 40 днів після закінчення кварталу.</i>"
    )

    from handlers.common import get_main_menu_keyboard

    await message.answer(
        text=result_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard()
    )
