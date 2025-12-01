from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import create_db_and_tables
from .routers import ai, appointment, analysis, user

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    print("Starting Service...")
    yield
    print("Shutting Down Service...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Med It Easy Backend is running!"}

app.include_router(ai.router)
app.include_router(appointment.router)
app.include_router(analysis.router)
app.include_router(user.router)
