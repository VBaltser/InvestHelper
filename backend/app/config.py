from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    tinkoff_token: str
    tinkoff_mode: str = "prod"
    # false — если корпоративный прокси/антивирус подменяет SSL-сертификат
    tinkoff_ssl_verify: bool = True
    # путь к корневому сертификату организации (альтернатива отключению проверки)
    tinkoff_ssl_ca_file: Optional[str] = None
    # прокси, если прямой доступ к API заблокирован: http://host:port
    tinkoff_https_proxy: Optional[str] = None
    tinkoff_api_timeout: float = 30.0

    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    chat_max_output_tokens: int = 8192
    chat_max_continuations: int = 2


settings = Settings()
