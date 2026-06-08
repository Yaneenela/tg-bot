import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command

from bot.config import settings
from bot.database import init_db
from bot.scheduler import start_scheduler
from bot.handlers import start, purchase, subscriptions, admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(purchase.router)
    dp.include_router(subscriptions.router)
    dp.include_router(admin.router)

    @dp.message(Command("admin"))
    async def admin_cmd(message: types.Message):
        from bot.handlers.admin import is_admin
        from bot.keyboards import admin_menu
        if await is_admin(message.from_user.id):
            await message.answer(
                "🔧 <b>Админ-панель</b>",
                reply_markup=admin_menu(),
            )
        else:
            await message.answer("⛔ Доступ запрещён")

    @dp.callback_query(lambda c: c.data == "back_main")
    async def back_main(callback: types.CallbackQuery):
        from bot.handlers.start import get_or_create_user
        from bot.keyboards import main_menu
        user = await get_or_create_user(
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.full_name,
        )
        await callback.message.edit_text(
            "🔐 <b>VPN Store</b>\n\n"
            "Быстрый и надёжный VPN на базе HAPP.\n"
            "Безлимитный трафик, выбор срока и устройств.",
            reply_markup=main_menu(user.is_admin),
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "back_duration")
    async def back_duration(callback: types.CallbackQuery):
        from bot.keyboards import duration_menu
        await callback.message.edit_text(
            "📋 <b>Выберите срок подписки:</b>\n\n"
            "Безлимитный трафик на всех тарифах.",
            reply_markup=duration_menu(),
        )
        await callback.answer()

    start_scheduler(bot)

    logger.info("Bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
