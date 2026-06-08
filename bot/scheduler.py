from datetime import datetime, timedelta
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database import async_session
from bot.models import Subscription
from bot.xui import xui_client

scheduler = AsyncIOScheduler()


async def check_expired():
    now = datetime.utcnow()
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.end_date < now,
            )
        )
        expired = result.scalars().all()

        for sub in expired:
            try:
                await xui_client.disable_client(sub.inbound_id, sub.client_uuid)
            except Exception:
                pass
            sub.is_active = False
            await session.merge(sub)

        await session.commit()


async def check_soon_expiring(bot):
    now = datetime.utcnow()
    soon = now + timedelta(days=3)
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).join(Subscription.user).where(
                Subscription.is_active == True,
                Subscription.end_date.between(now, soon),
            )
        )
        subs = result.scalars().all()

        for sub in subs:
            remaining = sub.days_remaining
            if remaining == 3 or remaining == 1:
                try:
                    await bot.send_message(
                        sub.user.telegram_id,
                        f"⚠️ <b>Подписка истекает через {remaining} дн.</b>\n\n"
                        f"📅 {sub.duration_days} дней, {sub.devices_count} уст.\n"
                        f"🗓 Истекает: {sub.end_date.strftime('%d.%m.%Y')}\n\n"
                        f"Нажмите /start и выберите «Мои подписки» → «Продлить».",
                    )
                except Exception:
                    pass


def start_scheduler(bot):
    scheduler.add_job(check_expired, "interval", hours=6, id="check_expired")
    scheduler.add_job(
        check_soon_expiring, "interval", hours=12, args=[bot], id="check_soon_expiring"
    )
    scheduler.start()
