import json
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database import async_session
from bot.models import Subscription, Payment, User
from bot.config import settings
from bot.xui import xui_client
from bot.yookassa import get_payment

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)


async def notify_user(bot, telegram_id: int, text: str):
    try:
        await bot.send_message(telegram_id, text)
    except Exception:
        pass


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
                    await notify_user(
                        bot, sub.user.telegram_id,
                        f"⚠️ <b>Подписка истекает через {remaining} дн.</b>\n\n"
                        f"📅 {sub.duration_days} дней, {sub.devices_count} уст.\n"
                        f"🗓 Истекает: {sub.end_date.strftime('%d.%m.%Y')}\n\n"
                        f"Нажмите /start и выберите «Мои подписки» → «Продлить».",
                    )
                except Exception:
                    pass


async def check_pending_payments(bot):
    async with async_session() as session:
        result = await session.execute(
            select(Payment).where(
                Payment.status == "pending",
                Payment.yookassa_payment_id.isnot(None),
            )
        )
        pending = result.scalars().all()

    for payment in pending:
        try:
            data = await get_payment(payment.yookassa_payment_id)
        except Exception:
            continue

        if not data:
            continue

        status = data.get("status")
        if status == "succeeded":
            await _activate_payment(payment, data.get("metadata", {}), bot)
        elif status == "canceled":
            async with async_session() as session:
                payment.status = "canceled"
                await session.merge(payment)
                await session.commit()


async def _activate_payment(payment, metadata, bot):
    tariff_str = metadata.get("tariff", "{}")
    try:
        tariff = json.loads(tariff_str)
    except json.JSONDecodeError:
        return

    days = tariff.get("days", 30)
    devices = tariff.get("devices", 1)
    sub_id = tariff.get("sub_id", uuid.uuid4().hex[:12])
    extend_sub_id = tariff.get("extend_sub_id")

    async with async_session() as session:
        payment = await session.merge(payment)
        if payment.status == "succeeded":
            return

        payment.status = "succeeded"
        payment.paid_at = datetime.utcnow()

        if extend_sub_id:
            result = await session.execute(
                select(Subscription).where(Subscription.id == extend_sub_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                user = await session.get(User, sub.user_id)
                now = datetime.utcnow()
                if now > sub.end_date:
                    sub.end_date = now + timedelta(days=days)
                else:
                    sub.end_date += timedelta(days=days)
                sub.is_active = True
                payment.subscription_id = sub.id
                await session.commit()

                await notify_user(
                    bot, user.telegram_id if user else 0,
                    f"✅ <b>Подписка продлена!</b>\n\n"
                    f"➕ Добавлено {days} дней\n"
                    f"📅 Новый срок до: {sub.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"🔗 <code>{sub.sub_link}</code>",
                )
            return

        inbounds = await xui_client.get_inbounds()
        if not inbounds:
            return

        inbound = inbounds[0]
        inbound_id = inbound["id"]
        email = f"tg_{payment.user_id}"
        client_uuid = uuid.uuid4().hex

        try:
            await xui_client.add_client(
                inbound_id=inbound_id,
                email=email,
                days=days,
                devices=devices,
                sub_id=sub_id,
            )
        except Exception as e:
            logger.error(f"Failed to add client to 3x-ui: {e}")
            return

        now = datetime.utcnow()
        sub_link = f"{settings.sub_url.rstrip('/')}/{sub_id}"

        new_sub = Subscription(
            user_id=payment.user_id,
            inbound_id=inbound_id,
            client_email=email,
            client_uuid=client_uuid,
            sub_id=sub_id,
            sub_link=sub_link,
            duration_days=days,
            devices_count=devices,
            total_price=payment.amount,
            start_date=now,
            end_date=now + timedelta(days=days),
            is_active=True,
        )
        session.add(new_sub)
        await session.flush()
        payment.subscription_id = new_sub.id
        await session.commit()

        user = await session.get(User, payment.user_id)
        await notify_user(
            bot, user.telegram_id if user else 0,
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"📅 {days} дней, {devices} устройств\n"
            f"🗓 Действует до: {new_sub.end_date.strftime('%d.%m.%Y')}\n\n"
            f"🔗 <b>Ваша ссылка для HAPP:</b>\n"
            f"<code>{sub_link}</code>\n\n"
            f"📌 Вставьте её в приложение HAPP и пользуйтесь.",
        )


def start_scheduler(bot):
    scheduler.add_job(check_expired, "interval", hours=6, id="check_expired")
    scheduler.add_job(
        check_soon_expiring, "interval", hours=12, args=[bot], id="check_soon_expiring"
    )
    scheduler.add_job(
        check_pending_payments, "interval", seconds=30, args=[bot],
        id="check_pending_payments",
    )
    scheduler.start()