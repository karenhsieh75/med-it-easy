from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlmodel import SQLModel, Session, select
from typing import List
from datetime import datetime
from ..database import get_session
from ..models import Appointment, AppointmentStatus
from ..utils import validate_business_hours

router = APIRouter(prefix="/api/appointment", tags=["預約系統"])


# Shared fields
class AppointmentBase(SQLModel):
    patient_id: int
    doctor_id: int
    date: str
    time: str
    department: str

# Create input
class AppointmentCreate(AppointmentBase):
    pass

# Update input
class AppointmentUpdate(SQLModel):
    date: Optional[str] = None
    time: Optional[str] = None
    department: Optional[str] = None
    status: Optional[AppointmentStatus] = None

# Response
class AppointmentPublic(AppointmentBase):
    id: int
    status: AppointmentStatus
    created_at: datetime


@router.post("/", response_model=AppointmentPublic)
def create_appointment(appointment_data: AppointmentCreate, session: Session = Depends(get_session)):
    # 驗證時間
    validate_business_hours(appointment_data.time)

    # 檢查該時段是否已被預約
    existing = session.exec(
        select(Appointment)
        .where(Appointment.doctor_id == appointment_data.doctor_id)
        .where(Appointment.date == appointment_data.date)
        .where(Appointment.time == appointment_data.time)
        .where(Appointment.status != AppointmentStatus.CANCELLED)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="此時段該醫師已有預約")

    # 寫入資料庫
    db_appointment = Appointment.model_validate(appointment_data)
    session.add(db_appointment)
    session.commit()
    session.refresh(db_appointment)
    return db_appointment


@router.get("/{appointment_id}", response_model=AppointmentPublic)
def get_appointment(appointment_id: int, session: Session = Depends(get_session)):
    appointment = session.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")
    return appointment


@router.get("/", response_model=List[AppointmentPublic])
def read_appointments(
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """
    取得預約列表，支援透過 patient_id, doctor_id 進行篩選
    """
    query = select(Appointment)
    
    if patient_id:
        query = query.where(Appointment.patient_id == patient_id)
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
        
    # 依照日期與時間排序 (新的在前)
    query = query.order_by(Appointment.date.desc(), Appointment.time.desc())
    
    appointments = session.exec(query).all()
    return appointments


@router.patch("/{appointment_id}", response_model=AppointmentPublic)
def update_appointment(
    appointment_id: int, 
    appointment_data: AppointmentUpdate, 
    session: Session = Depends(get_session)
):
    db_appointment = session.get(Appointment, appointment_id)
    if not db_appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")

    # 如果有改時間，才驗證時間
    if appointment_data.time is not None:
        validate_business_hours(appointment_data.time)

    # 欄位更新
    update_data = appointment_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_appointment, key, value)

    session.add(db_appointment)
    session.commit()
    session.refresh(db_appointment)
    return db_appointment


@router.delete("/{appointment_id}")
def delete_appointment(appointment_id: int, session: Session = Depends(get_session)):
    db_appointment = session.get(Appointment, appointment_id)
    if not db_appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")
        
    session.delete(db_appointment)
    session.commit()
    return {"ok": True, "message": "預約已刪除"}
