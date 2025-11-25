from datetime import datetime
from sqlmodel import Session, select
from app.database import engine, create_db_and_tables
from app.models import User, UserRole, Appointment, AppointmentStatus, AnalysisRecord


def create_fake_data():
    # 1. 確保資料表存在
    create_db_and_tables()

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
            User(
                username=f"dr_lee_{user_offset + 2}",
                password_hash="secret123",
                full_name="李小美醫師",
                role=UserRole.DOCTOR,
                department="外科",
            ),
            User(
                username=f"dr_chen_{user_offset + 3}",
                password_hash="secret123",
                full_name="陳育成醫師",
                role=UserRole.DOCTOR,
                department="小兒科",
            ),
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

        # --- 5. 建立分析紀錄 (AnalysisRecord) ---
        sample_analysis = AnalysisRecord(
            patient_id=patients[0].id,
            analysis_type="skin_tone",
            analysis_result='{"best_match": "Warm Sand", "warm_cool_neutral_base": {"warm": 55.2, "cool": 18.3, "neutral": 26.5}}',
        )
        session.add(sample_analysis)
        session.commit()
        print("已新增 1 筆分析紀錄")

        print("資料生成完畢！")


if __name__ == "__main__":
    create_fake_data()
