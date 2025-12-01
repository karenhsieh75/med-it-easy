from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from .database import create_db_and_tables
from .routers import ai, appointment, analysis, user, medical_records, symptoms

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

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

app.include_router(user.router)
app.include_router(appointment.router)
app.include_router(analysis.router)
app.include_router(symptoms.router)
app.include_router(ai.router)
app.include_router(medical_records.router)

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')
