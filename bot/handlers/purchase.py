import uuid
import json
from aiogram import Router, F, types
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Payment
from bot.config import settings
from bot.keyboards import duration_menu, devices_menu, confirm_purchase, back_button
from bot.yookassa import create_payment

router = Router()


@router.callback_query(F.data == "buy")
async def buy_start(callback: types.CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
    if not user or user.is_banned:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "📋 <b>Выберите срок подписки:</b>\n\n"
        "Безлимитный трафик на всех тарифах.",
        reply_markup=duration_menu(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dur:"))
async def choose_duration(callback: types.CallbackQuery):
    days = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"📱 <b>Выберите количество устройств:</b>\n\n"
        f"Срок: {days} дней\n"
        f"Базовая цена (1-{settings.base_devices} уст.): {settings.duration_prices[days]} ₽\n"
        f"Доп. устройство: +{settings.extra_device_price} ₽",
        reply_markup=devices_menu(days),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dev:"))
async def choose_devices(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    days = int(parts[1])
    devices = int(parts[2])
    price = settings.calc_price(days, devices)

    await callback.message.edit_text(
        f"<b>Подтверждение заказа:</b>\n\n"
        f"📅 Срок: {days} дней\n"
        f"📱 Устройств: {devices}\n"
        f"💾 Трафик: безлимит\n"
        f"💰 Сумма: <b>{price} ₽</b>\n\n"
        f"Подтвердите оплату.",
        reply_markup=confirm_purchase(days, devices, price),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def process_payment(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    days = int(parts[1])
    devices = int(parts[2])
    price = int(parts[3])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
    if not user or user.is_banned:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    sub_id = uuid.uuid4().hex[:12]
    tariff_data = json.dumps({"days": days, "devices": devices, "sub_id": sub_id})

    try:
        payment = await create_payment(
            amount=price,
            description=f"VPN {days}дн/{devices}уст",
            user_id=user.id,
            tariff_data=tariff_data,
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка создания платежа: {e}\n\nПопробуйте позже.",
            reply_markup=back_button("back_main"),
        )
        await callback.answer()
        return

    if not payment:
        await callback.message.edit_text(
            "❌ Платёжная система недоступна. Попробуйте позже.",
            reply_markup=back_button("back_main"),
        )
        await callback.answer()
        return

    async with async_session() as session:
        db_payment = Payment(
            user_id=user.id,
            amount=price,
            yookassa_payment_id=payment["id"],
            status="pending",
            description=f"VPN {days}дн/{devices}уст",
        )
        session.add(db_payment)
        await session.commit()

    await callback.message.edit_text(
        f"💳 <b>Оплата</b>\n\n"
        f"Тариф: {days} дней, {devices} уст.\n"
        f"Сумма: {price} ₽\n\n"
        f"Ссылка для оплаты:\n{payment['url']}\n\n"
        f"<i>После оплаты подписка активируется автоматически.</i>",
        reply_markup=back_button("back_main"),
    )
    await callback.answer()
