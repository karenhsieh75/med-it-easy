import base64
import json
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..services.card_generator import SkinToneCardGenerator
from ..services.skin_tone import analyze_face_color
from ..database import get_session
from ..models import AnalysisRecord, Appointment, User, UserRole

router = APIRouter(prefix="/api/analysis", tags=["膚色分析"])

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CARD_TEMPLATE = ASSETS_DIR / "c.png"
CARD_FONT = ASSETS_DIR / "Iansui-Regular.ttf"
LLM_PLACEHOLDER = "保持規律作息、補充水分並記得防曬，下一次回診一起檢視膚況。"


class AnalysisRecordPublic(BaseModel):
    id: int
    patient_id: int
    analysis_type: str
    analysis_result: dict
    created_at: str

    class Config:
        from_attributes = True


@router.post("/skin-tone", response_model=AnalysisRecordPublic)
async def analyze_skin_tone(
    patient_id: int = Form(...),
    appointment_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    上傳臉部照片，依 doctor.json 規則得出最先匹配的分析結果，並輸出小卡。
    """
    patient = session.get(User, patient_id)
    if not patient or patient.role != UserRole.PATIENT:
        raise HTTPException(status_code=404, detail="找不到此患者")

    try:
        file_bytes = await file.read()
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        raise HTTPException(status_code=400, detail="無法讀取上傳的影像")

    if img is None:
        raise HTTPException(status_code=400, detail="影像解碼失敗或格式不支援")

    analysis = analyze_face_color(img)
    if analysis.get("status") != "analysis_complete":
        raise HTTPException(status_code=400, detail=analysis.get("message", "分析失敗"))

    # 取得預約資訊：優先使用傳入 appointment_id，否則抓該患者最新一筆
    appointment: Optional[Appointment] = None
    if appointment_id:
        appointment = session.get(Appointment, appointment_id)
        if not appointment or appointment.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="找不到對應的預約資料供卡片生成")
    else:
        appointment = session.exec(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .order_by(Appointment.created_at.desc())
        ).first()

    appointment_fields = {
        "app_id": f"{appointment.id:02d}" if appointment else "N/A",
        "app_date": f"{appointment.date} {appointment.time}" if appointment else "N/A",
        "app_category": appointment.department if appointment else "N/A",
    }

    result = analysis.get("result", {})
    diagnosis_text = f"{result.get('explanation', '')} {result.get('advice', '')}".strip()

    try:
        generator = SkinToneCardGenerator(CARD_TEMPLATE, CARD_FONT)
        rose_base64 = analysis.get("_analysis_rose_plot_base64")
        if not rose_base64:
            raise HTTPException(status_code=500, detail="缺少玫瑰圖資料，無法生成卡片")
        rose_bytes = base64.b64decode(rose_base64)
        analysis_card_base64 = generator.generate_card(
            rose_chart_bytes=rose_bytes,
            diagnosis_text=diagnosis_text,
            appointment_fields=appointment_fields,
            llm_advice=LLM_PLACEHOLDER,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 回傳給前端的完整結果（含圖片）
    analysis_result_response = {
        "status": analysis.get("status"),
        "result": result,
        "appointment_context": appointment_fields,
        "analysis_card_base64": analysis_card_base64,
    }
    # 存 DB 的精簡版（不存 base64）
    analysis_result_db = {
        "status": analysis.get("status"),
        "result": result,
        "appointment_context": appointment_fields,
    }

    record = AnalysisRecord(
        patient_id=patient_id,
        analysis_type="skin_tone",
        analysis_result=json.dumps(analysis_result_db),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "analysis_type": record.analysis_type,
        "analysis_result": analysis_result_response,
        "created_at": record.created_at.isoformat(),
    }


@router.get("/records", response_model=list[AnalysisRecordPublic])
def list_records(
    patient_id: Optional[int] = None,
    analysis_type: Optional[str] = None,
    session: Session = Depends(get_session),
):
    query = select(AnalysisRecord)
    if patient_id:
        query = query.where(AnalysisRecord.patient_id == patient_id)
    if analysis_type:
        query = query.where(AnalysisRecord.analysis_type == analysis_type)
    records = session.exec(query.order_by(AnalysisRecord.created_at.desc())).all()
    return [
        {
            "id": r.id,
            "patient_id": r.patient_id,
            "analysis_type": r.analysis_type,
            "analysis_result": json.loads(r.analysis_result or "{}"),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/records/{record_id}", response_model=AnalysisRecordPublic)
def get_record(record_id: int, session: Session = Depends(get_session)):
    record = session.get(AnalysisRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="找不到指定的分析紀錄")
    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "analysis_type": record.analysis_type,
        "analysis_result": json.loads(record.analysis_result or "{}"),
        "created_at": record.created_at.isoformat(),
    }
