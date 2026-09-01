from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import ApiException, api_exception_handler
from app.routers import health

app = FastAPI(title="Peblo TV Mini API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(ApiException, api_exception_handler)
app.include_router(health.router)
