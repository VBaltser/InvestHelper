from app.config import settings

PROD_BASE_URL = "https://invest-public-api.tbank.ru/rest"
SANDBOX_BASE_URL = "https://sandbox-invest-public-api.tbank.ru/rest"


def get_base_url() -> str:
    if settings.tinkoff_mode.lower() == "sandbox":
        return SANDBOX_BASE_URL
    return PROD_BASE_URL
