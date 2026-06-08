from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import async_session
from bot.models import User
from bot.keyboards import main_menu

router = Router()


async def get_or_create_user(tg_id: int, username: str | None,
                             full_name: str | None) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=tg_id,
                username=username,
                full_name=full_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    is_admin = user.is_admin
    await message.answer(
        "🔐 <b>VPN Store</b>\n\n"
        "Быстрый и надёжный VPN на базе HAPP.\n"
        "Безлимитный трафик, выбор срока и устройств.",
        reply_markup=main_menu(is_admin),
    )
