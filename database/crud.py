from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, RequestForm, AuthSession
from config import OTP_EXPIRY_SECONDS
from utils.text_utils import normalize_phone

# --- КОРИСТУВАЧІ (USERS) ---

async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
    # Очищуємо номер телефону для пошуку (залишаємо тільки цифри)
    clean_phone = "".join(filter(str.isdigit, phone))
    # Шукаємо користувача, номер якого містить ці цифри в кінці
    result = await session.execute(select(User))
    users = result.scalars().all()
    for user in users:
        if user.phone_number:
            user_clean = "".join(filter(str.isdigit, user.phone_number))
            if user_clean.endswith(clean_phone) or clean_phone.endswith(user_clean):
                return user
    return None

async def get_or_create_user(
    session: AsyncSession, 
    user_id: int, 
    username: Optional[str] = None, 
    first_name: Optional[str] = None, 
    last_name: Optional[str] = None
) -> User:
    user = await get_user_by_id(session, user_id)
    if not user:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def update_user_phone(
    session: AsyncSession, 
    user_id: int, 
    phone_number: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> User:
    user = await get_user_by_id(session, user_id)
    normalized = normalize_phone(phone_number)
    if not user:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone_number=normalized
        )
        session.add(user)
    else:
        user.phone_number = normalized
    await session.commit()
    await session.refresh(user)
    return user


# --- ЗАЯВКИ (REQUEST FORMS) ---

async def create_request_form(
    session: AsyncSession,
    name: str,
    phone: str,
    text: str,
    user_id: Optional[int] = None,
    source: str = "bot"
) -> RequestForm:
    normalized = normalize_phone(phone)
    request_form = RequestForm(
        user_id=user_id,
        name=name,
        phone=normalized,
        text=text,
        source=source
    )
    session.add(request_form)
    await session.commit()
    await session.refresh(request_form)
    return request_form

async def get_request_form_by_id(session: AsyncSession, request_id: int) -> Optional[RequestForm]:
    result = await session.execute(select(RequestForm).where(RequestForm.id == request_id))
    return result.scalar_one_or_none()

async def update_request_status(
    session: AsyncSession,
    request_id: int,
    status: str,
    reply_text: Optional[str] = None
) -> Optional[RequestForm]:
    request_form = await get_request_form_by_id(session, request_id)
    if request_form:
        request_form.status = status
        if reply_text is not None:
            request_form.reply_text = reply_text
        await session.commit()
        await session.refresh(request_form)
    return request_form

async def get_user_requests(session: AsyncSession, user_id: int, limit: int = 5) -> List[RequestForm]:
    result = await session.execute(
        select(RequestForm)
        .where(RequestForm.user_id == user_id)
        .order_by(RequestForm.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# --- СЕСІЇ АУТЕНТИФІКАЦІЇ (AUTH SESSIONS / OTP) ---

async def create_auth_session(session: AsyncSession, phone_number: str, otp_code: str) -> AuthSession:
    normalized = normalize_phone(phone_number)
    # Видаляємо попередні неактивні сесії для цього номера
    await session.execute(
        select(AuthSession).where(AuthSession.phone_number == normalized)
    )
    
    auth_session = AuthSession(
        phone_number=normalized,
        otp_code=otp_code
    )
    session.add(auth_session)
    await session.commit()
    await session.refresh(auth_session)
    return auth_session

async def verify_otp_code(session: AsyncSession, phone_number: str, code: str) -> bool:
    # Очищуємо номер
    clean_phone = "".join(filter(str.isdigit, phone_number))
    
    # Визначаємо час ліміту дії коду
    expiry_time = datetime.utcnow() - timedelta(seconds=OTP_EXPIRY_SECONDS)
    
    # Шукаємо діючу сесію
    result = await session.execute(
        select(AuthSession)
        .where(AuthSession.otp_code == code)
        .where(AuthSession.is_verified == False)
        .where(AuthSession.created_at >= expiry_time)
        .order_by(AuthSession.created_at.desc())
    )
    
    sessions = result.scalars().all()
    for s in sessions:
        s_clean = "".join(filter(str.isdigit, s.phone_number))
        if s_clean.endswith(clean_phone) or clean_phone.endswith(s_clean):
            s.is_verified = True
            await session.commit()
            return True
            
    return False
