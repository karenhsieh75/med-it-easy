from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from ..database import get_session
from ..models import SymptomLog, Appointment, MedicalRecord

load_dotenv()

router = APIRouter(prefix="/api/ai", tags=["AI 問診"])

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

class ChatRequest(BaseModel):
    appointment_id: int
    message: str

@router.post("/chat")
async def chat_with_ai(request: ChatRequest, session: Session = Depends(get_session)):
    # 1. 檢查預約是否存在
    appointment = session.get(Appointment, request.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="找不到此預約")

    try:
        # 2. 儲存使用者的訊息到資料庫
        user_log = SymptomLog(
            appointment_id=request.appointment_id,
            sender_role="patient",
            content=request.message
        )
        session.add(user_log)
        session.commit() # 先存進去，確保歷史紀錄有這筆

        # 3. 從資料庫撈出過去的歷史對話
        logs = session.exec(
            select(SymptomLog)
            .where(SymptomLog.appointment_id == request.appointment_id)
            .order_by(SymptomLog.created_at)
        ).all()

        # 4. 轉換成 Gemini 看得懂的格式 (user/model)
        # 我們的 DB 存 "patient"/"ai"，Gemini 要 "user"/"model"
        gemini_history = []
        for log in logs:
            role = "user" if log.sender_role == "patient" else "model"
            gemini_history.append({
                "role": role,
                "parts": [{"text": log.content}]
            })
        
        # 將歷史紀錄組合成一個大的 Prompt
        system_prompt = """
        你現在是一個醫療問診專案的 AI 助手。請根據使用者的症狀描述與對話歷史，執行以下任務並回傳 JSON 格式：

        1. disease (判斷疾病)：推測可能的疾病名稱（若資訊不足請填寫「待觀察」）。
        2. advice (給予建議/補問)：
           - 如果資訊不足以判斷，請針對症狀提出「補問」（例如：請問持續多久了？）。
           - 如果資訊足夠，請提供簡短護理建議。
           - 語氣請保持親切、像一位專業的護理師。

        注意：不需要任何 Markdown 標記，直接回傳 JSON 物件。
        """
        
        # 把對話紀錄串起來變成文本
        history_text = ""
        for log in logs:
            role_name = "病患" if log.sender_role == "patient" else "AI助手"
            history_text += f"{role_name}: {log.content}\n"
            
        full_prompt = f"{system_prompt}\n\n【對話歷史紀錄】\n{history_text}\n\nAI助手 (請回答):"

        # 5. 呼叫 AI
        response = model.generate_content(full_prompt)
        ai_reply = response.text # 取得包含 Markdown 的原始字串

        # 6. 清理字串，移除 Markdown 封裝
        cleaned_text = ai_reply.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text.removeprefix("```json").lstrip()     
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text.removesuffix("```").rstrip()

        # 7. 嘗試解析清理後的 JSON
        try:
            result = json.loads(cleaned_text)
            ai_disease = result.get("disease", "待觀察")
            ai_advice = result.get("advice", "抱歉，AI 建議無法生成。")
        
        except json.JSONDecodeError:
            # 如果清理後還是失敗，表示 AI 回傳的內容格式徹底錯誤
            ai_disease = "解析錯誤"
            ai_advice = "系統無法解析 AI 回應的 JSON 格式，請再試一次，或更換 Prompt。"
        
        # 8. 儲存 AI 的回覆到資料庫 (只存乾淨的 advice)
        ai_log = SymptomLog(
            appointment_id=request.appointment_id,
            sender_role="ai",
            content=ai_advice 
        )
        session.add(ai_log)

        # 9. 更新 MedicalRecord
        medical_record = session.exec(
            select(MedicalRecord).where(MedicalRecord.appointment_id == request.appointment_id)
        ).first()
        
        if not medical_record:
            medical_record = MedicalRecord(appointment_id=request.appointment_id)
            session.add(medical_record)
        
        medical_record.ai_disease_prediction = ai_disease
        session.add(medical_record)
        
        session.commit()

        # 10. 回傳分開的資料
        return {
            "disease": ai_disease, 
            "advice": ai_advice
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))