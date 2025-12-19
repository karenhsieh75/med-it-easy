from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy import inspect, text
from app.database import engine, create_db_and_tables
from app.models import (
    User,
    UserRole,
    Appointment,
    AppointmentStatus,
    AnalysisRecord,
    MedicalRecord,
)

# 前五筆預約資料都是測試用的
def create_fake_data():
    # 1. 確保資料表存在
    create_db_and_tables()
    ensure_medical_record_columns()

    with Session(engine) as session:
        # 以現有人數做 offset，避免 username 唯一鍵衝突
        existing_users = session.exec(select(User)).all()
        user_offset = len(existing_users)

        print("開始插入測試資料...")

        # --- 2. 建立醫師 ---
        doctors = [
            User(
                username=f"dr_wang_{user_offset + 1}",  
                password_hash="secret123",
                full_name="王大明醫師",
                role=UserRole.DOCTOR,
                department="內科",
            ),
            # username= dr_wang_1 , password= secret123

            User(
                username=f"dr_lee_{user_offset + 2}",
                password_hash="secret123",
                full_name="李小美醫師",
                role=UserRole.DOCTOR,
                department="外科",
            ),
            # username= dr_lee_2 , password= secret123

            User(
                username=f"dr_chen_{user_offset + 3}",
                password_hash="secret123",
                full_name="陳育成醫師",
                role=UserRole.DOCTOR,
                department="小兒科",
            ),
            # username= dr_chen_3 , password= secret123
        ]
        session.add_all(doctors)
        session.commit()
        for doc in doctors:
            session.refresh(doc)
        print(f"已新增 {len(doctors)} 位醫師（累積使用者: {len(existing_users) + len(doctors)}）")

        # --- 3. 建立病患 ---
        patients = [
            User(
                username=f"patient_a_{user_offset + 1}",
                password_hash="123456",
                full_name="張偉",
                role=UserRole.PATIENT,
            ),
            User(
                username=f"patient_b_{user_offset + 2}",
                password_hash="123456",
                full_name="林佳",
                role=UserRole.PATIENT,
            ),
            User(
                username=f"patient_c_{user_offset + 3}",
                password_hash="123456",
                full_name="陳芳",
                role=UserRole.PATIENT,
            ),
        ]
        session.add_all(patients)
        session.commit()
        for p in patients:
            session.refresh(p)
        print(f"已新增 {len(patients)} 位病患")

        # --- 4. 建立預約 ---
        today = datetime.now().date()
        appointments = [
            Appointment(
                patient_id=patients[0].id,
                doctor_id=doctors[0].id,
                date=str(today),
                time="09:00",
                department="內科",
                status=AppointmentStatus.PENDING,
            ),
            Appointment(
                patient_id=patients[1].id,
                doctor_id=doctors[0].id,
                date=str(today),
                time="10:00",
                department="內科",
                status=AppointmentStatus.PENDING,
            ),
            Appointment(
                patient_id=patients[2].id,
                doctor_id=doctors[1].id,
                date=str(today),
                time="14:00",
                department="外科",
                status=AppointmentStatus.COMPLETED,
            ),
            Appointment(
                patient_id=patients[0].id,
                doctor_id=doctors[2].id,
                date=str(today),
                time="15:00",
                department="小兒科",
                status=AppointmentStatus.CANCELLED,
            ),
            Appointment(
                patient_id=patients[1].id,
                doctor_id=doctors[2].id,
                date=str(today),
                time="16:00",
                department="小兒科",
                status=AppointmentStatus.PENDING,
            ),
        ]
        session.add_all(appointments)
        session.commit()
        print(f"已新增 {len(appointments)} 筆預約資料")

        # --- 5. 建立病歷資料 (MedicalRecord) ---
        medical_records = [
            MedicalRecord(
                appointment_id=appointments[0].id,
                ai_summary="Patient reports mild seasonal allergies with intermittent cough.",
                ai_disease_prediction="Allergic rhinitis; monitor for bronchitis progression.",
                ai_advice="Increase hydration, consider over-the-counter antihistamine if symptoms persist.",
                doctor_diagnosis="Allergic rhinitis",
                prescription="Cetirizine 10mg daily for 7 days",
            ),
            MedicalRecord(
                appointment_id=appointments[1].id,
                ai_summary="Low-grade fever and sore throat beginning yesterday, no rash noted.",
                ai_disease_prediction="Viral pharyngitis; strep less likely without exudate.",
                ai_advice="Warm fluids and rest; seek follow-up if fever >38.5C for 48 hours.",
                doctor_diagnosis=None,
                prescription=None,
            ),
            MedicalRecord(
                appointment_id=appointments[2].id,
                ai_summary="Post-operative wound check with mild redness, no discharge.",
                ai_disease_prediction="Normal healing; watch for infection signs.",
                ai_advice="可能是過度疲憊囉~ 早睡早起有益身體健康，並記得多多補充蔬果。另外，每天多喝水也是必須的，祝您早日康復",
                doctor_diagnosis="Uneventful post-op recovery",
                prescription="Topical mupirocin twice daily for 5 days",
            ),
        ]
        session.add_all(medical_records)
        session.commit()
        print(f"已新增 {len(medical_records)} 筆病歷資料")

        # --- 6. 建立分析紀錄 (AnalysisRecord) ---
        sample_analysis = AnalysisRecord(
            patient_id=patients[0].id,
            analysis_type="skin_tone",
            analysis_result='{"best_match": "Warm Sand", "warm_cool_neutral_base": {"warm": 55.2, "cool": 18.3, "neutral": 26.5}}',
        )
        session.add(sample_analysis)
        session.commit()
        print("已新增 1 筆分析紀錄")

def ensure_medical_record_columns():
    """
    Ensure legacy SQLite files have the latest MedicalRecord columns.
    SQLite does not auto-migrate on create_all, so add missing columns on the fly.
    """
    inspector = inspect(engine)
    existing_cols = {col["name"] for col in inspector.get_columns("medical_records")}
    needed = {
        "ai_summary": "TEXT",
        "ai_disease_prediction": "TEXT",
        "ai_advice": "TEXT",
        "doctor_diagnosis": "TEXT",
        "prescription": "TEXT",
    }
    with engine.begin() as conn:
        for col_name, col_type in needed.items():
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE medical_records ADD COLUMN {col_name} {col_type}"))

        print("醫療紀錄表欄位檢查完成")


if __name__ == "__main__":
    create_fake_data()
