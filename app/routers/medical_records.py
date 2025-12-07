from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Session, select
from typing import Optional
from datetime import datetime

from ..database import get_session
from ..models import (
    MedicalRecord,
    Appointment,
    AppointmentStatus,
)
from ..services.ai_service import generate_ai_summary

router = APIRouter(prefix="/api/medical_record", tags=["病歷與診斷"])


# Base model
class MedicalRecordBase(SQLModel):
    appointment_id: int


class MedicalRecordCreate(MedicalRecordBase):
    pass


class MedicalRecordUpdate(SQLModel):
    doctor_diagnosis: Optional[str] = None
    prescription: Optional[str] = None


class MedicalRecordPublic(MedicalRecordBase):
    id: int
    ai_summary: Optional[str]
    ai_disease_prediction: Optional[str]
    ai_advice: Optional[str]
    doctor_diagnosis: Optional[str]
    prescription: Optional[str]
    created_at: datetime


# =============================
# ✔ POST: 新增病歷
# =============================
@router.post("/", response_model=MedicalRecordPublic)
def create_record(record_data: MedicalRecordCreate, session: Session = Depends(get_session)):

    # 確認 appointment 是否存在
    appointment = session.get(Appointment, record_data.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到 appointment")

    # 生成 AI summary 和 prediction
    ai_summary, ai_disease_prediction, ai_advice = generate_ai_summary(record_data.appointment_id, session)

    db_record = MedicalRecord.model_validate(record_data)
    db_record.ai_summary = ai_summary
    db_record.ai_disease_prediction = ai_disease_prediction
    db_record.ai_advice = ai_advice

    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record


# =============================
# ✔ GET: 用 appointment_id 查病歷
# =============================
@router.get("/appointment/{appointment_id}", response_model=MedicalRecordPublic)
def get_record_by_appointment(appointment_id: int, session: Session = Depends(get_session)):
    record = session.exec(
        select(MedicalRecord).where(MedicalRecord.appointment_id == appointment_id)
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="找不到病歷")
    return record


# =============================
# ✔ PATCH: 更新診斷（完成看診 → 診斷完成）
# =============================
@router.patch("/{record_id}", response_model=MedicalRecordPublic)
def update_diagnosis(record_id: int, record_data: MedicalRecordUpdate, session: Session = Depends(get_session)):
    db_record = session.get(MedicalRecord, record_id)
    if not db_record:
        raise HTTPException(status_code=404, detail="找不到病歷")

    # 更新欄位
    update_data = record_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_record, key, value)

    # **重點：該 appointment 設為 COMPLETED**
    appointment = session.get(Appointment, db_record.appointment_id)
    appointment.status = AppointmentStatus.COMPLETED
    session.add(appointment)

    session.add(db_record)
    session.commit()
    session.refresh(db_record)

    return db_record


# =============================
# ✔ DELETE: 刪除病歷
# =============================
@router.delete("/{record_id}")
def delete_record(record_id: int, session: Session = Depends(get_session)):
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="找不到病歷")

    session.delete(record)
    session.commit()
    return {"ok": True, "message": "病歷已刪除"}
