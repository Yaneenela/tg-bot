from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    bot_token: str

    # 3x-ui
    xui_url: str
    xui_token: str
    xui_insecure: bool = True
    xui_base_path: str = "/panel"

    # ЮKassa
    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_return_url: str

    # Subscription
    sub_url: str
    sub_domain: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///bot/db.sqlite3"

    # Pricing
    price_30d: int = 100
    price_60d: int = 200
    price_90d: int = 300
    extra_device_price: int = 30
    max_devices: int = 10
    base_devices: int = 3

    # Admin
    admin_ids: list[int] = []

    @property
    def duration_prices(self) -> dict[int, int]:
        return {30: self.price_30d, 60: self.price_60d, 90: self.price_90d}

    def calc_price(self, days: int, devices: int) -> int:
        base = self.duration_prices.get(days, self.price_30d)
        extra = max(0, devices - self.base_devices) * self.extra_device_price
        return base + extra


settings = Settings()
