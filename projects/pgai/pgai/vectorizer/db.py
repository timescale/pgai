from dataclasses import dataclass


@dataclass
class ConnInfo:
    """Connection information for a PostgreSQL database"""

    host: str
    port: int
    role: str
    password: str
    db_name: str
    ssl_mode: str = "require"

    @property
    def url(self) -> str:
        """Return the connection URL for the database"""
        return f"postgres://{self.role}:{self.password}@{self.host}:{self.port}/{self.db_name}?sslmode={self.ssl_mode}"
