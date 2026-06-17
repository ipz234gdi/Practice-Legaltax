from aiogram.fsm.state import State, StatesGroup

class UserForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_text = State()

class AdminStates(StatesGroup):
    in_queue = State()
    waiting_for_reply_text = State()  # Очікування відповіді на заявку від адміна

class CalculatorStates(StatesGroup):
    waiting_for_revenue = State()     # Очікування введення суми доходу

class CabinetStates(StatesGroup):
    waiting_for_phone = State()       # Очікування вводу телефону в кабінеті
