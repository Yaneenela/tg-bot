from bot.config import settings
import uuid

try:
    from yookassa import Configuration, Payment as YooPayment
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key
    YOOKASSA_AVAILABLE = True
except Exception:
    YOOKASSA_AVAILABLE = False


async def create_payment(amount: int, description: str,
                         user_id: int, tariff_data: str,
                         return_url: str | None = None) -> dict | None:
    if not YOOKASSA_AVAILABLE:
        return None

    try:
        payment = YooPayment.create({
            "amount": {
                "value": f"{amount / 100:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or settings.yookassa_return_url,
            },
            "capture": True,
            "description": description[:128],
            "metadata": {
                "user_id": str(user_id),
                "tariff": tariff_data,
            },
        }, uuid.uuid4().hex)

        return {
            "id": payment.id,
            "url": payment.confirmation.confirmation_url,
            "status": payment.status,
        }
    except Exception as e:
        raise Exception(f"YooKassa error: {e}")


async def get_payment_status(payment_id: str) -> str | None:
    if not YOOKASSA_AVAILABLE:
        return None
    try:
        payment = YooPayment.find_one(payment_id)
        return payment.status
    except Exception:
        return None


async def get_payment(payment_id: str) -> dict | None:
    if not YOOKASSA_AVAILABLE:
        return None
    try:
        payment = YooPayment.find_one(payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "metadata": dict(payment.metadata) if payment.metadata else {},
        }
    except Exception:
        return None
