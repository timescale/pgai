from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


@app.post("/")
async def execute_vectorizer(vectorizer: dict):
    return {"id": vectorizer['id']}

