from sqlmodel import Session, select
from typing import Tuple
import json
from ..models import Symptom, ChatLog
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash')

def generate_ai_summary(appointment_id: int, session: Session) -> Tuple[str, str]:
    ai_summary = None
    ai_disease_prediction = None
    
    try:
        # 1. 收集症狀資料
        symptom = session.exec(
            select(Symptom).where(Symptom.appointment_id == appointment_id)
        ).first()

        # 2. 收集對話歷史
        chat_logs = session.exec(
            select(ChatLog)
            .where(ChatLog.appointment_id == appointment_id)
            .order_by(ChatLog.created_at)
        ).all()

        # 3. 組合資料給 AI
        context_parts = []

        if symptom:
            symptom_info = f"""
            【症狀報告】
            症狀描述: {symptom.description}
            症狀清單: {', '.join(symptom.symptoms)}
            持續時間: {symptom.duration}
            嚴重程度: {symptom.severity}
            """
            if symptom.notes:
                symptom_info += f"備註: {symptom.notes}\n"
            context_parts.append(symptom_info)

        if chat_logs:
            chat_history = "\n【對話歷史】\n"
            for log in chat_logs:
                role_name = "病患" if log.sender_role == "patient" else "AI助手"
                chat_history += f"{role_name}: {log.content}\n"
            context_parts.append(chat_history)

        # 只有在有資料時才呼叫 AI
        if context_parts:
            full_context = "\n".join(context_parts)

            system_prompt = """
            你是一位專業的醫療 AI 助手。
            請根據提供的症狀報告和對話歷史,完成以下任務並以 JSON 格式回傳:

            1. **summary** (病歷摘要):
            - 簡潔地總結患者的主要症狀、病史和重要資訊
            - 約 100-200 字
            - 使用專業但易懂的醫療術語

            2. **disease_prediction** (疾病推測):
            - 基於症狀和對話,推測最可能的疾病或診斷
            - 如果資訊不足,填寫「待觀察」或「需進一步檢查」
            - 可以列出 1-3 個可能性,以可能性排序

            注意: 不需要任何 Markdown 標記,直接回傳 JSON 物件。

            格式範例:
            {
            "summary": "患者主訴...",
            "disease_prediction": "初步推測為..."
            }
            """

            full_prompt = (
                f"{system_prompt}\n\n{full_context}\n\n請提供分析結果:"
            )

            # 呼叫 AI
            response = model.generate_content(full_prompt)
            ai_reply = response.text.strip()

            # 清理 Markdown 封裝
            if ai_reply.startswith("```json"):
                ai_reply = ai_reply.removeprefix("```json").lstrip()
            if ai_reply.endswith("```"):
                ai_reply = ai_reply.removesuffix("```").rstrip()

            # 解析 JSON
            try:
                result = json.loads(ai_reply)
                ai_summary = result.get("summary", "")
                ai_disease_prediction = result.get(
                    "disease_prediction", "待觀察"
                )
            except json.JSONDecodeError:
                # 解析失敗時使用預設值
                ai_summary = "AI 摘要生成失敗"
                ai_disease_prediction = "待觀察"

    except Exception as e:
        # 如果 AI 生成失敗,不影響病歷建立,只記錄錯誤
        print(f"AI 生成失敗: {str(e)}")
        ai_summary = "AI 摘要生成失敗"
        ai_disease_prediction = "待觀察"

    return ai_summary, ai_disease_prediction