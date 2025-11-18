from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Session, select
from typing import List
from ..database import get_session
from ..models import Appointment

router = APIRouter(prefix="/api/appointment", tags=["預約系統"])

class AppointmentBase(SQLModel):
    patient_id: int
    doctor_id: int
    date: str
    time: str
    department: str

class AppointmentCreate(AppointmentBase):
    pass

@router.post("/", response_model=Appointment)
def create_appointment(appointment_data: AppointmentCreate, session: Session = Depends(get_session)):
    appointment = Appointment.model_validate(appointment_data)
    session.add(appointment)
    session.commit()
    session.refresh(appointment)
    return appointment

@router.get("/", response_model=List[Appointment])
def read_appointments(session: Session = Depends(get_session)):
    appointments = session.exec(select(Appointment)).all()
    return appointments

@router.get("/doctor/{doctor_name}")
def get_doctor_schedule(doctor_name: str, session: Session = Depends(get_session)):
    statement = select(Appointment).where(Appointment.doctor == doctor_name)
    results = session.exec(statement).all()
    return results