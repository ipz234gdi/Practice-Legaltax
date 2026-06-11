from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

# Створюємо асинхронний двигун бази даних
engine = create_async_engine(DATABASE_URL, echo=False)

# Створюємо фабрику сесій
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Базовий клас для моделей
class Base(DeclarativeBase):
    pass

# Функція для отримання сесії БД (Dependency/Context Manager)
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
