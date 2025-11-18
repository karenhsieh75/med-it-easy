from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import create_db_and_tables

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    print("Staring Service...")
    yield
    print("Shutting Down Service...")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"message": "Med It Easy Backend is running!"}