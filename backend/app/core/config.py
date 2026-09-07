import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Try loading from .env first, then fallback to .env.example
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.example"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./sih_drug_tester.db"
    
    JWT_SECRET_KEY: str = "8ca636e76cf0a2d212133496cbb24ef86cb4da6f1b3ff75df5b68dfa43fb6487"
    JWT_REFRESH_SECRET_KEY: str = "f50d18b671a5fb2eb3da9ff02e077c5cbe8ba90635b71db3f0896014e7dc27e3"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    OTP_EXPIRY_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 3
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    # Hex-encoded Ed25519 private & public keys
    # Private key is 32 bytes (64 hex characters)
    # Public key is 32 bytes (64 hex characters)
    ED25519_PRIVATE_KEY: str = "8fcf2c51b7537b98d1a1236ea8924e2ffeb97feefc32da4ba4613abce9a3a789"
    ED25519_PUBLIC_KEY: str = "f782ba984a9c80d19992efbe43665dfb1285311e5a59f1be0be73f1a0b3b4a25"

    CORS_ORIGINS: Union[str, List[str]] = ["*"]

    ENVIRONMENT: str = "development"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

settings = Settings()

