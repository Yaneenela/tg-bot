from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import settings


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Купить подписку", callback_data="buy"))
    builder.row(InlineKeyboardButton(text="📦 Мои подписки", callback_data="mysubs"))
    builder.row(InlineKeyboardButton(text="❓ Помощь", callback_data="help"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="🔧 Админ-панель", callback_data="admin"))
    return builder.as_markup()


def duration_menu() -> InlineKeyboardMarkup:
    prices = settings.duration_prices
    builder = InlineKeyboardBuilder()
    for days, price in sorted(prices.items()):
        builder.row(InlineKeyboardButton(
            text=f"{days} дней — {price} ₽",
            callback_data=f"dur:{days}"
        ))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="back_main"))
    return builder.as_markup()


def devices_menu(days: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in range(1, settings.max_devices + 1):
        extra = max(0, d - settings.base_devices) * settings.extra_device_price
        total = settings.duration_prices[days] + extra
        label = f"{d} уст. — {total} ₽"
        builder.add(InlineKeyboardButton(text=label, callback_data=f"dev:{days}:{d}"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="back_duration"))
    return builder.as_markup()


def confirm_purchase(days: int, devices: int, price: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Оплатить картой", callback_data=f"pay:{days}:{devices}:{price}"))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data=f"dev:{days}"))
    return builder.as_markup()


def subscription_actions(sub_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Продлить", callback_data=f"extend:{sub_id}"))
    builder.row(InlineKeyboardButton(text="📋 Копировать ссылку", callback_data=f"copy:{sub_id}"))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="mysubs"))
    return builder.as_markup()


def extend_duration_menu(sub_id: int) -> InlineKeyboardMarkup:
    prices = settings.duration_prices
    builder = InlineKeyboardBuilder()
    for days, price in sorted(prices.items()):
        builder.row(InlineKeyboardButton(
            text=f"+{days} дней — {price} ₽",
            callback_data=f"extpay:{sub_id}:{days}:{price}"
        ))
    builder.row(InlineKeyboardButton(text="← Назад", callback_data=f"sub:{sub_id}"))
    return builder.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users:0"))
    builder.row(InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments:0"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="⚙️ Проверка сервера", callback_data="admin_server"))
    builder.row(InlineKeyboardButton(text="← Главное меню", callback_data="back_main"))
    return builder.as_markup()


def back_button(callback: str = "back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="← Назад", callback_data=callback))
    return builder.as_markup()
