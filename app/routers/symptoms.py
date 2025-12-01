from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional
from ..database import get_session
from ..models import Symptom, Appointment

router = APIRouter(prefix="/api/symptoms", tags=["症狀報告"])

# Create input
class SymptomCreate(BaseModel):
    appointment_id: int
    description: str
    symptoms: List[str]
    duration: str
    severity: str
    notes: Optional[str] = None
    analysis_record_id: Optional[int] = None  # 選填：如果有做影像分析，就會傳這個 ID

# Response
class SymptomPublic(BaseModel):
    id: int
    appointment_id: int
    description: str
    symptoms: List[str]
    duration: str
    severity: str
    notes: Optional[str] = None
    analysis_record_id: Optional[int] = None
    created_at: str


@router.post("/", response_model=SymptomPublic)
def submit_symptom(data: SymptomCreate, session: Session = Depends(get_session)):
    """
    提交症狀報告
    """
    # 檢查預約是否存在
    appointment = session.get(Appointment, data.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")

    # 檢查是否已經填寫過
    existing = session.exec(select(Symptom).where(Symptom.appointment_id == data.appointment_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="此預約已提交過症狀報告")

    new_symptom = Symptom(
        appointment_id=data.appointment_id,
        analysis_record_id=data.analysis_record_id,
        description=data.description,
        symptoms=data.symptoms,
        duration=data.duration,
        severity=data.severity,
        notes=data.notes
    )
    
    session.add(new_symptom)
    session.commit()
    session.refresh(new_symptom)
    
    return SymptomPublic(
        id=new_symptom.id,
        appointment_id=new_symptom.appointment_id,
        description=new_symptom.description,
        symptoms=new_symptom.symptoms,
        duration=new_symptom.duration,
        severity=new_symptom.severity,
        notes=new_symptom.notes,
        analysis_record_id=new_symptom.analysis_record_id,
        created_at=new_symptom.created_at.isoformat()
    )

@router.get("/{appointment_id}", response_model=SymptomPublic)
def get_symptom(appointment_id: int, session: Session = Depends(get_session)):
    """
    透過 appointment_id 查詢症狀報告
    """
    symptom = session.exec(select(Symptom).where(Symptom.appointment_id == appointment_id)).first()
    
    if not symptom:
        raise HTTPException(status_code=404, detail="此預約尚未填寫症狀")
        
    return SymptomPublic(
        id=symptom.id,
        appointment_id=symptom.appointment_id,
        description=symptom.description,
        symptoms=symptom.symptoms,
        duration=symptom.duration,
        severity=symptom.severity,
        notes=symptom.notes,
        analysis_record_id=symptom.analysis_record_id,
        created_at=symptom.created_at.isoformat()
    )