from sqlmodel import Session, select
from app.database import engine, create_db_and_tables
from app.models import User, UserRole, Appointment, AppointmentStatus

def create_fake_data():
    # 1. 初始化資料庫 (如果表不存在則建立)
    create_db_and_tables()

    with Session(engine) as session:
        # 檢查是否已經有資料，避免重複寫入
        existing_user = session.exec(select(User)).first()
        if existing_user:
            print("資料庫中已有資料，跳過假資料生成。")
            return

        print("開始生成假資料...")

        # --- 2. 建立醫生 (Doctors) ---
        doctors = [
            User(
                username="dr_wang",
                password_hash="secret123",
                full_name="王大明醫師",
                role=UserRole.DOCTOR,
                department="內科"
            ),
            User(
                username="dr_lee",
                password_hash="secret123",
                full_name="李小華醫師",
                role=UserRole.DOCTOR,
                department="外科"
            ),
            User(
                username="dr_chen",
                password_hash="secret123",
                full_name="陳美美醫師",
                role=UserRole.DOCTOR,
                department="小兒科"
            )
        ]
        for doc in doctors:
            session.add(doc)
        session.commit() # 先 Commit 才能拿到 doctor_id
        
        # 重新整理物件以取得 ID
        for doc in doctors:
            session.refresh(doc)
        
        print(f"已建立 {len(doctors)} 位醫生")

        # --- 3. 建立病患 (Patients) ---
        patients = [
            User(
                username="patient_a",
                password_hash="123456",
                full_name="張三",
                role=UserRole.PATIENT
            ),
            User(
                username="patient_b",
                password_hash="123456",
                full_name="李四",
                role=UserRole.PATIENT
            ),
            User(
                username="patient_c",
                password_hash="123456",
                full_name="王五",
                role=UserRole.PATIENT
            )
        ]
        for p in patients:
            session.add(p)
        session.commit()
        
        for p in patients:
            session.refresh(p)

        print(f"已建立 {len(patients)} 位病患")

        # --- 4. 建立預約 (Appointments) ---
        appointments = [
            # 王醫師 (內科) 的預約
            Appointment(
                patient_id=patients[0].id, # 張三
                doctor_id=doctors[0].id,   # 王醫師
                date="2025-11-25",
                time="09:00",
                department="內科",
                status=AppointmentStatus.PENDING
            ),
            Appointment(
                patient_id=patients[1].id, # 李四
                doctor_id=doctors[0].id,   # 王醫師
                date="2025-11-25",
                time="10:00",
                department="內科",
                status=AppointmentStatus.PENDING
            ),
            # 李醫師 (外科) 的預約
            Appointment(
                patient_id=patients[2].id, # 王五
                doctor_id=doctors[1].id,   # 李醫師
                date="2025-11-26",
                time="14:00",
                department="外科",
                status=AppointmentStatus.COMPLETED # 已完成
            ),
            # 陳醫師 (小兒科) 的預約
            Appointment(
                patient_id=patients[0].id, # 張三
                doctor_id=doctors[2].id,   # 陳醫師
                date="2025-11-27",
                time="15:00",
                department="小兒科",
                status=AppointmentStatus.CANCELLED # 已取消
            ),
             Appointment(
                patient_id=patients[1].id, # 李四
                doctor_id=doctors[2].id,   # 陳醫師
                date="2025-11-27",
                time="16:00",
                department="小兒科",
                status=AppointmentStatus.PENDING
            ),
        ]

        for appt in appointments:
            session.add(appt)
        
        session.commit()
        print(f"已建立 {len(appointments)} 筆預約資料")
        print("資料生成完畢！")

if __name__ == "__main__":
    create_fake_data()