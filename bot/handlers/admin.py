from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from bot.database import async_session
from bot.models import User, Subscription, Payment
from bot.config import settings
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from bot.keyboards import admin_menu, back_button
from bot.xui import xui_client

router = Router()


class BroadcastFSM(StatesGroup):
    waiting_message = State()


async def is_admin(tg_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = result.scalar_one_or_none()
        return bool(user and user.is_admin)


@router.callback_query(F.data == "admin")
async def admin_panel(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        active_subs = await session.scalar(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        )
        payments_today = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == "succeeded",
                func.date(Payment.paid_at) == func.date("now"),
            )
        )
        payments_month_str = func.strftime("%Y-%m", Payment.paid_at)
        now_month_str = func.strftime("%Y-%m", func.now())
        payments_month = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == "succeeded",
                payments_month_str == now_month_str,
            )
        )

    try:
        online = await xui_client.get_online_clients()
        online_count = len(online)
    except Exception:
        online_count = 0

    text = (
        f"<b>📊 Статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users or 0}\n"
        f"✅ Активных подписок: {active_subs or 0}\n"
        f"🟢 Онлайн сейчас: {online_count}\n"
        f"💰 Доход сегодня: {payments_today or 0} ₽\n"
        f"💰 Доход за месяц: {payments_month or 0} ₽"
    )
    await callback.message.edit_text(text, reply_markup=back_button("admin"))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_users:"))
async def admin_users(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    page = int(callback.data.split(":")[1])
    page_size = 10

    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.id).offset(page * page_size).limit(page_size)
        )
        users = result.scalars().all()
        total = await session.scalar(select(func.count(User.id)))

    if not users:
        await callback.message.edit_text("Пользователей нет.", reply_markup=back_button("admin"))
        await callback.answer()
        return

    text = f"<b>👥 Пользователи (стр. {page + 1})</b>\n\n"
    for u in users:
        badge = "🛡 " if u.is_admin else ""
        banned = " ⛔" if u.is_banned else ""
        text += f"{badge}{u.telegram_id} @{u.username or '—'}{banned}\n"

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.row(InlineKeyboardButton(text="← Назад", callback_data=f"admin_users:{page - 1}"))
    if len(users) == page_size:
        builder.row(InlineKeyboardButton(text="Вперёд →", callback_data=f"admin_users:{page + 1}"))
    builder.row(InlineKeyboardButton(text="← К админке", callback_data="admin"))

    await callback.message.edit_text(text.strip(), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_payments:"))
async def admin_payments(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    page = int(callback.data.split(":")[1])
    page_size = 10

    async with async_session() as session:
        result = await session.execute(
            select(Payment).order_by(Payment.created_at.desc())
            .offset(page * page_size).limit(page_size)
        )
        payments = result.scalars().all()

    if not payments:
        await callback.message.edit_text("Платежей нет.", reply_markup=back_button("admin"))
        await callback.answer()
        return

    text = f"<b>💰 Платежи (стр. {page + 1})</b>\n\n"
    for p in payments:
        status_icon = "✅" if p.status == "succeeded" else "⏳"
        text += f"{status_icon} {p.amount}₽ — {p.description} — {p.created_at.strftime('%d.%m %H:%M')}\n"

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.row(InlineKeyboardButton(text="←", callback_data=f"admin_payments:{page - 1}"))
    if len(payments) == page_size:
        builder.row(InlineKeyboardButton(text="→", callback_data=f"admin_payments:{page + 1}"))
    builder.row(InlineKeyboardButton(text="← К админке", callback_data="admin"))

    await callback.message.edit_text(text.strip(), reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await state.set_state(BroadcastFSM.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Напишите сообщение для отправки всем пользователям.\n"
        "Или отправьте /cancel для отмены.",
        reply_markup=back_button("admin"),
    )
    await callback.answer()


@router.message(BroadcastFSM.waiting_message, F.text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_banned == False))
        user_ids = result.scalars().all()

    sent = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(
                uid, f"📢 <b>Рассылка</b>\n\n{message.text}"
            )
            sent += 1
        except Exception:
            pass

    await state.clear()
    await message.answer(f"✅ Рассылка отправлена {sent} из {len(user_ids)} пользователям.")


@router.message(BroadcastFSM.waiting_message, F.text == "/cancel")
async def admin_broadcast_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@router.callback_query(F.data == "admin_server")
async def admin_server(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    try:
        inbounds = await xui_client.get_inbounds()
        online = await xui_client.get_online_clients()
        text = (
            f"<b>⚙️ Проверка сервера</b>\n\n"
            f"✅ 3x-ui: доступен\n"
            f"📦 Inbound'ов: {len(inbounds)}\n"
            f"🟢 Онлайн: {len(online)}\n"
            f"🔗 URL: {settings.xui_url}"
        )
    except Exception as e:
        text = f"<b>⚙️ Проверка сервера</b>\n\n❌ 3x-ui: ошибка\n<code>{e}</code>"

    await callback.message.edit_text(text, reply_markup=back_button("admin"))
    await callback.answer()


@router.callback_query(F.data == "admin_check")
async def admin_check(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    await callback.message.edit_text("🔍 Проверяю подписки... Подождите.")
    await callback.answer()

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.is_active == True)
        )
        subs = result.scalars().all()

    if not subs:
        await callback.message.edit_text(
            "✅ Активных подписок нет, расхождений нет.",
            reply_markup=back_button("admin"),
        )
        return

    mismatches = []
    checked = 0
    errors = 0

    for sub in subs:
        checked += 1
        try:
            xui_expiry_ms = await xui_client.xui_get_expiry_ms(sub.client_email)
            if xui_expiry_ms is None:
                mismatches.append((sub, "нет в 3x-ui"))
                continue

            db_expiry_s = int(sub.end_date.timestamp())
            xui_expiry_s = xui_expiry_ms // 1000

            diff = abs(db_expiry_s - xui_expiry_s)
            if diff > 120:
                mismatches.append((sub, f"расхождение {diff // 60} мин"))
        except Exception:
            errors += 1

    text = (
        f"<b>🔍 Результат проверки</b>\n\n"
        f"Проверено: {checked}\n"
        f"Расхождений: {len(mismatches)}\n"
        f"Ошибок: {errors}\n"
    )

    if mismatches:
        text += "\n<b>Расхождения:</b>\n"
        for sub, reason in mismatches[:10]:
            text += f"• {sub.client_email} — {reason}\n"
        if len(mismatches) > 10:
            text += f"  ... и ещё {len(mismatches) - 10}\n"

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🛠 Исправить все", callback_data="admin_fix_confirm"
        ))
        builder.row(InlineKeyboardButton(text="← К админке", callback_data="admin"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(
            text + "\n✅ Все подписки синхронизированы.",
            reply_markup=back_button("admin"),
        )


@router.callback_query(F.data == "admin_fix_confirm")
async def admin_fix_confirm(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Да, исправить", callback_data="admin_fix_do"
    ))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="admin_check"))
    await callback.message.edit_text(
        "⚠️ <b>Исправить все расхождения?</b>\n\n"
        "Бот обновит expiryTime в 3x-ui по данным из базы.\n"
        "Отменить будет нельзя.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_fix_do")
async def admin_fix_do(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    await callback.message.edit_text("🛠 Исправляю... Подождите.")
    await callback.answer()

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.is_active == True)
        )
        subs = result.scalars().all()

    fixed = 0
    errors = 0

    for sub in subs:
        try:
            found = await xui_client.find_client_by_email(sub.client_email)
            if not found:
                errors += 1
                continue

            xui_expiry = found["client"].get("expiryTime", 0)
            db_expiry = int(sub.end_date.timestamp() * 1000)

            if abs(xui_expiry - db_expiry) > 120_000:
                await xui_client.xui_update_expiry(
                    inbound_id=found["inbound_id"],
                    client_id=found["client"]["id"],
                    expiry_ms=db_expiry,
                    devices=sub.devices_count,
                )
                fixed += 1
        except Exception:
            errors += 1

    text = (
        f"<b>🛠 Исправление завершено</b>\n\n"
        f"✅ Исправлено: {fixed}\n"
        f"❌ Ошибок: {errors}"
    )
    await callback.message.edit_text(text, reply_markup=back_button("admin"))
