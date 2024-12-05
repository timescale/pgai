def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"
