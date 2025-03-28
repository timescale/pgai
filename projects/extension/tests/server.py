import os

import dotenv
from fastapi import FastAPI, Header, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

dotenv.load_dotenv()

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


@app.get("/api/v1/projects/secrets")
async def get_secrets(secret_name: str = Header(None, alias="Secret-Name")):
    if not secret_name:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Secret-Name header is required"},
        )

    # For now, we'll just return the test key if the secret_name matches
    if secret_name == "OPENAI_API_KEY" or secret_name == "OPENAI_API_KEY_2":
        return {secret_name: "test"}
    elif secret_name == "OPENAI_API_KEY_REAL":
        return {secret_name: os.environ["OPENAI_API_KEY"]}
    elif secret_name == "COHERE_API_KEY_REAL":
        return {secret_name: os.environ["COHERE_API_KEY"]}
    elif secret_name == "ANTHROPIC_API_KEY_REAL":
        return {secret_name: os.environ["ANTHROPIC_API_KEY"]}
    elif secret_name == "ERROR_SECRET":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "error secret"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Secret '{secret_name}' not found"},
        )
