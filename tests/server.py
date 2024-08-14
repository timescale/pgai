from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


class VectorizerRequest(BaseModel):
    id: int


@app.post("/")
async def execute_vectorizer(request: VectorizerRequest):
    return {"id": request.id}

