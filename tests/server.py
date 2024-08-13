from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


class ExecuteVectorizerRequest(BaseModel):
    id: int


@app.post("/")
async def execute_vectorizer(request: ExecuteVectorizerRequest):
    return {"id": request.id}

