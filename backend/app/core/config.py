from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "אוצר ישראל"
    database_url: str = "sqlite:///./otzar_israel.db"
    cors_origins: str = "http://localhost:5173"
    sefaria_books_index_url: str = "https://raw.githubusercontent.com/Sefaria/Sefaria-Export/master/books.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
