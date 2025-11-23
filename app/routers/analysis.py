from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
import numpy as np
import cv2
import json

from ..database import get_session
from ..models import AnalysisRecord, User, UserRole
from ..analysis.skin_tone import (
    analyze_face_color,
    generate_plot_base64,
    generate_rose_plot_base64,
    skin_palette,
)

router = APIRouter(prefix="/api/analysis", tags=["分析"])


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
    patient_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    上傳人臉圖片，執行膚色分析並建立 AnalysisRecord。
    """
    patient = session.get(User, patient_id)
    if not patient or patient.role != UserRole.PATIENT:
        raise HTTPException(status_code=404, detail="找不到此病患")

    try:
        file_bytes = await file.read()
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        raise HTTPException(status_code=400, detail="無法解析上傳的影像檔")

    if img is None:
        raise HTTPException(status_code=400, detail="影像格式不支援或解碼失敗")

    analysis = analyze_face_color(img)
    if analysis.get("status") != "analysis_complete":
        raise HTTPException(status_code=400, detail=analysis.get("message", "分析失敗"))

    # 產生圖表（如需在前端顯示）
    weights = analysis.pop("_raw_weights")
    group_sum = analysis.pop("_raw_group_sum")
    best_idx = analysis.pop("_raw_best_idx")

    analysis["analysis_plot_base64"] = generate_plot_base64(
        skin_palette, weights, group_sum, best_idx
    )
    analysis["analysis_rose_plot_base64"] = generate_rose_plot_base64(
        skin_palette, weights
    )

    record = AnalysisRecord(
        patient_id=patient_id,
        analysis_type="skin_tone",
        analysis_result=json.dumps(analysis),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "analysis_type": record.analysis_type,
        "analysis_result": analysis,
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
    # 轉回 dict 給 response_model
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
        raise HTTPException(status_code=404, detail="找不到分析紀錄")
    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "analysis_type": record.analysis_type,
        "analysis_result": json.loads(record.analysis_result or "{}"),
        "created_at": record.created_at.isoformat(),
    }
