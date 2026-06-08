import json
from datetime import datetime, timedelta
from aiogram import Router, F, types
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Subscription, Payment
from bot.config import settings
from bot.keyboards import (
    subscription_actions, extend_duration_menu, main_menu, back_button,
)
from bot.xui import xui_client
from bot.yookassa import create_payment

router = Router()


@router.callback_query(F.data == "mysubs")
async def my_subscriptions(callback: types.CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала /start", show_alert=True)
            return

        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.is_active == True,
            ).order_by(Subscription.end_date.desc())
        )
        subs = result.scalars().all()

    if not subs:
        await callback.message.edit_text(
            "📦 У вас нет активных подписок.\n\n"
            "Нажмите «Купить подписку», чтобы оформить.",
            reply_markup=back_button("back_main"),
        )
        await callback.answer()
        return

    text = "<b>📦 Ваши подписки:</b>\n\n"
    for sub in subs:
        remaining = sub.days_remaining
        status_icon = "✅" if sub.is_active and not sub.is_expired else "🔴"
        text += (
            f"{status_icon} <b>{sub.duration_days} дней, {sub.devices_count} уст.</b>\n"
            f"📅 до {sub.end_date.strftime('%d.%m.%Y')} "
            f"(осталось {remaining} дн.)\n"
            f"🔗 <code>{sub.sub_link}</code>\n\n"
        )

    await callback.message.edit_text(
        text.strip(),
        reply_markup=back_button("back_main"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:"))
async def sub_detail(callback: types.CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()

    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    remaining = sub.days_remaining
    status = "✅ Активна" if sub.is_active and not sub.is_expired else "🔴 Истекла"
    text = (
        f"<b>Подписка #{sub.id}</b>\n\n"
        f"Статус: {status}\n"
        f"📅 Срок: {sub.duration_days} дней\n"
        f"📱 Устройств: {sub.devices_count}\n"
        f"🗓 Создана: {sub.start_date.strftime('%d.%m.%Y')}\n"
        f"🗓 Истекает: {sub.end_date.strftime('%d.%m.%Y')}\n"
        f"⏳ Осталось: {remaining} дн.\n\n"
        f"🔗 Ссылка:\n<code>{sub.sub_link}</code>"
    )
    await callback.message.edit_text(text, reply_markup=subscription_actions(sub.id))
    await callback.answer()


@router.callback_query(F.data.startswith("extend:"))
async def extend_sub(callback: types.CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "🔄 <b>Выберите, на сколько продлить:</b>\n\n"
        "Новый срок прибавится к текущей дате окончания.",
        reply_markup=extend_duration_menu(sub_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("extpay:"))
async def extend_payment(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    sub_id = int(parts[1])
    days = int(parts[2])
    price = int(parts[3])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return

    tariff_data = json.dumps({"days": days, "devices": 0, "extend_sub_id": sub_id})

    try:
        payment = await create_payment(
            amount=price,
            description=f"Продление VPN +{days}дн",
            user_id=user.id,
            tariff_data=tariff_data,
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=back_button("mysubs"),
        )
        await callback.answer()
        return

    if not payment:
        await callback.message.edit_text(
            "❌ Платёжная система недоступна.",
            reply_markup=back_button("mysubs"),
        )
        await callback.answer()
        return

    async with async_session() as session:
        db_payment = Payment(
            user_id=user.id,
            subscription_id=sub_id,
            amount=price,
            yookassa_payment_id=payment["id"],
            status="pending",
            description=f"Продление VPN +{days}дн",
        )
        session.add(db_payment)
        await session.commit()

    await callback.message.edit_text(
        f"💳 <b>Продление подписки</b>\n\n"
        f"+{days} дней к текущему сроку\n"
        f"Сумма: {price} ₽\n\n"
        f"Ссылка для оплаты:\n{payment['url']}\n\n"
        f"<i>После оплаты срок автоматически продлится.</i>",
        reply_markup=back_button("mysubs"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("copy:"))
async def copy_link(callback: types.CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()

    if not sub:
        await callback.answer("Не найдено", show_alert=True)
        return

    await callback.answer(f"Ссылка скопирована. Отправь её в HAPP.", show_alert=True)


@router.callback_query(F.data == "help")
async def help_handler(callback: types.CallbackQuery):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Как подключиться:\n"
        "1. Скачай <b>HAPP</b> (Android / Windows)\n"
        "2. Купи подписку в меню «Купить подписку»\n"
        "3. После оплаты получи ссылку\n"
        "4. Вставь её в HAPP → Готово\n\n"
        "По всем вопросам — @admin"
    )
    await callback.message.edit_text(text, reply_markup=back_button("back_main"))
    await callback.answer()
