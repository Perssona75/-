import re
from datetime import datetime, date

# -------------------------
# Проверка имени
# -------------------------
def validate_name(name: str) -> bool:
    """
    Имя может содержать буквы (кириллица или латиница), пробел и дефис.
    Длина 2-50 символов.
    """
    if not name:
        return False
    s = name.strip()
    if not (2 <= len(s) <= 50):
        return False
    # Разрешаем буквы, пробел и дефис
    if re.fullmatch(r"[A-Za-zА-Яа-яЁё\- ]+", s):
        return True
    return False

# -------------------------
# Проверка фамилии
# -------------------------
def validate_last_name(last_name: str) -> bool:
    """
    Использует те же правила, что имя
    """
    return validate_name(last_name)

# -------------------------
# Проверка даты рождения ДД.ММ.ГГГГ
# -------------------------
def validate_birth_date_ddmmyyyy(date_str: str) -> bool:
    """
    Проверяет дату рождения в формате ДД.MM.ГГГГ
    и что она не в будущем
    """
    if not date_str:
        return False
    try:
        birth = datetime.strptime(date_str.strip(), "%d.%m.%Y").date()
    except ValueError:
        return False
    return birth <= date.today()

# -------------------------
# Проверка даты назначения диагноза (YYYY-MM-DD)
# -------------------------
def validate_date_not_future(date_str: str) -> bool:
    """
    Проверяет дату в формате YYYY-MM-DD
    и что она не в будущем
    """
    if not date_str:
        return False
    try:
        d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return False
    return d <= date.today()

# -------------------------
# Проверка текста диагноза
# -------------------------
def validate_diagnosis_text(text: str) -> bool:
    """
    Название диагноза:
    - буквы, цифры, пробел, дефис, запятая, точка, скобки, двоеточие
    - минимум 3 символа, максимум 200
    - хотя бы одна буква
    """
    if not text:
        return False
    s = text.strip()
    if not (3 <= len(s) <= 200):
        return False
    # запрещённые символы
    if re.search(r"[<>@#$%^&*_+=\\\/]", s):
        return False
    # хотя бы одна буква
    if not re.search(r"[A-Za-zА-Яа-яЁё]", s):
        return False
    return True
