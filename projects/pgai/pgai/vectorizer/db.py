from dataclasses import dataclass


@dataclass
class ConnInfo:
    host: str
    port: int
    role: str
    password: str
    db_name: str
    ssl_mode: str = "require"

    @property
    def url(self) -> str:
        return f"postgres://{self.role}:{self.password}@{self.host}:{self.port}/{self.db_name}?sslmode={self.ssl_mode}"
