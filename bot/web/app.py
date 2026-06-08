import json
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Subscription, Payment
from bot.config import settings
from bot.xui import xui_client
from bot.yookassa import YOOKASSA_AVAILABLE

web_app = FastAPI(title="VPN Bot Webhooks")


async def notify_user(bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text)
    except Exception:
        pass


@web_app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    if not YOOKASSA_AVAILABLE:
        return {"ok": False, "error": "YooKassa not configured"}

    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid json"}

    event = body.get("event")
    if event != "payment.succeeded":
        return {"ok": True}

    payment_obj = body.get("object", {})
    payment_id = payment_obj.get("id")
    metadata = payment_obj.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    tariff_data = metadata.get("tariff", "{}")

    async with async_session() as session:
        result = await session.execute(
            select(Payment).where(Payment.yookassa_payment_id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment or payment.status == "succeeded":
            return {"ok": True}

        payment.status = "succeeded"
        payment.paid_at = datetime.utcnow()

        tariff = json.loads(tariff_data)
        days = tariff.get("days", 30)
        devices = tariff.get("devices", 1)
        sub_id = tariff.get("sub_id", uuid.uuid4().hex[:12])
        extend_sub_id = tariff.get("extend_sub_id")

        if extend_sub_id:
            result = await session.execute(
                select(Subscription).where(Subscription.id == extend_sub_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                user_result = await session.execute(
                    select(User).where(User.id == sub.user_id)
                )
                user = user_result.scalar_one_or_none()
                now = datetime.utcnow()
                if now > sub.end_date:
                    sub.end_date = now + timedelta(days=days)
                else:
                    sub.end_date += timedelta(days=days)
                sub.is_active = True
                payment.subscription_id = sub.id
                await session.commit()

                await notify_user(
                    request.app.state.bot,
                    user.telegram_id if user else 0,
                    f"✅ <b>Подписка продлена!</b>\n\n"
                    f"➕ Добавлено {days} дней\n"
                    f"📅 Новый срок до: {sub.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"🔗 <code>{sub.sub_link}</code>",
                )
                return {"ok": True}

        inbounds = await xui_client.get_inbounds()
        if not inbounds:
            return {"ok": False, "error": "no inbounds"}

        inbound = inbounds[0]
        inbound_id = inbound["id"]
        email = f"tg_{user_id}"
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
            return {"ok": False, "error": str(e)}

        now = datetime.utcnow()
        sub_link = f"{settings.sub_url.rstrip('/')}/{sub_id}"

        new_sub = Subscription(
            user_id=user_id,
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

        await notify_user(
            request.app.state.bot,
            user_id,
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"📅 {days} дней, {devices} устройств\n"
            f"🗓 Действует до: {new_sub.end_date.strftime('%d.%m.%Y')}\n\n"
            f"🔗 <b>Ваша ссылка для HAPP:</b>\n"
            f"<code>{sub_link}</code>\n\n"
            f"📌 Вставьте её в приложение HAPP и пользуйтесь.",
        )

    return {"ok": True}
