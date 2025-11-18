from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
import google.generativeai as genai
import os
from dotenv import load_dotenv
from ..database import get_session
from ..models import SymptomLog, Appointment

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
        你現在是一個醫療問診專案的 AI 助手。
        請根據使用者的症狀描述與對話歷史，執行以下任務：

        1. 【判斷疾病】：推測可能的疾病名稱（若資訊不足可寫「待觀察」）。
        2. 【給予建議】：提供簡短的護理建議或就醫指引，如果你還未成功判斷出疾病，請不要給予建議，問使用者其他問題以達到判斷病因的目的。

        ⚠️ 重要回覆格式規定：
        請務必使用 "###SEGMENT###" 符號將疾病名稱與建議分開。
        格式如下：
        [疾病名稱]###SEGMENT###[給使用者的親切建議]

        範例：
        感冒###SEGMENT###建議多喝溫開水，並多休息。...
        """
        
        # 把對話紀錄串起來變成文本
        history_text = ""
        for log in logs:
            role_name = "病患" if log.sender_role == "patient" else "AI助手"
            history_text += f"{role_name}: {log.content}\n"
            
        full_prompt = f"{system_prompt}\n\n【對話歷史紀錄】\n{history_text}\n\nAI助手 (請回答):"

        # 5. 呼叫 AI
        response = model.generate_content(full_prompt)
        ai_reply = response.text

        # 6. 儲存 AI 的回覆到資料庫
        ai_log = SymptomLog(
            appointment_id=request.appointment_id,
            sender_role="ai",
            content=ai_reply
        )
        session.add(ai_log)
        session.commit()

        return {"reply": ai_reply}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))