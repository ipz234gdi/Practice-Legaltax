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

def normalize_phone(phone: str) -> str:
    """
    Нормалізує номер телефону до формату +380XXXXXXXXX для українських номерів
    або +XXXXXXXXXXXX для міжнародних номерів.
    """
    if not phone:
        return ""
    
    # Залишаємо тільки цифри
    digits = "".join(filter(str.isdigit, phone))
    
    # Якщо номер починається з 380 і має 12 цифр
    if len(digits) == 12 and digits.startswith("380"):
        return f"+{digits}"
    # Якщо номер починається з 0 і має 10 цифр (наприклад, 0684877221)
    elif len(digits) == 10 and digits.startswith("0"):
        return f"+38{digits}"
    # Якщо номер має 9 цифр (наприклад, 684877221)
    elif len(digits) == 9:
        return f"+380{digits}"
    # Якщо номер починається з 80 і має 11 цифр (наприклад, 80684877221)
    elif len(digits) == 11 and digits.startswith("80"):
        return f"+3{digits}"
    # Будь-який інший міжнародний номер залишаємо як є (додаємо + на початку, якщо немає)
    else:
        if phone.strip().startswith("+"):
            return phone.strip()
        return f"+{digits}" if digits else phone.strip()

def format_phone(phone: str) -> str:
    """
    Приводить номер телефону до красивого формату +38 (0XX) XXX-XX-XX
    """
    if not phone:
        return ""
    
    # Залишаємо тільки цифри
    digits = "".join(filter(str.isdigit, phone))
    
    # Якщо номер починається з 380 і має 12 цифр
    if len(digits) == 12 and digits.startswith("380"):
        return f"+38 (0{digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"
    # Якщо номер має 10 цифр (наприклад, 0991234567)
    elif len(digits) == 10 and digits.startswith("0"):
        return f"+38 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    # Якщо номер має 9 цифр (наприклад, 684877221)
    elif len(digits) == 9:
        return f"+38 (0{digits[0:2]}) {digits[2:5]}-{digits[5:7]}-{digits[7:9]}"
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
