import re

def escape_markdown(text: str) -> str:
    """
    Екранує спеціальні символи для Telegram MarkdownV2.
    Спеціальні символи: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    """
    if not text:
        return ""
    
    # Регулярний вираз для пошуку спеціальних символів MarkdownV2
    escape_chars = r"[_*\[\]()~`#\+\-\=\|\{\}\.\!>]"
    return re.sub(escape_chars, r"\\\g<0>", text)

def format_phone(phone: str) -> str:
    """
    Приводить номер телефону до красивого формату +38 (0XX) XXX-XX-XX
    """
    # Залишаємо тільки цифри
    digits = "".join(filter(str.isdigit, phone))
    
    # Якщо номер починається з 380 і має 12 цифр
    if len(digits) == 12 and digits.startswith("380"):
        return f"+38 ({digits[3:6]}) {digits[6:9]}-{digits[9:11]}-{digits[11:13]}"
    # Якщо номер має 10 цифр (наприклад, 0991234567)
    elif len(digits) == 10 and digits.startswith("0"):
        return f"+38 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    # Інакше повертаємо вихідний номер з плюсом на початку
    return f"+{digits}" if not phone.startswith("+") else phone

def escape_markdown_code(text: str) -> str:
    """
    Екранує символи для використання всередині блоків коду `...` у MarkdownV2.
    Екрануються тільки `, \\ та /
    """
    if not text:
        return ""
    return str(text).replace("\\", "\\\\").replace("`", "\\`").replace("/", "\\/")

