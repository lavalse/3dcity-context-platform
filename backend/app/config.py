from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://citydb:citydb@localhost:5432/citydb"
    anthropic_api_key: str = ""
    query_row_limit: int = 1000
    query_timeout_seconds: int = 30

    @property
    def use_llm(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.startswith("sk-ant-"))

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
