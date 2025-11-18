from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

# --- Enums ---

class UserRole(str, Enum):
    """Defines user roles for access control."""
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class AppointmentStatus(str, Enum):
    """Tracks the lifecycle of an appointment."""
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# --- Models ---

class User(SQLModel, table=True):
    """Represents system users (Patients and Doctors)."""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    full_name: str
    role: UserRole
    department: Optional[str] = None  # Only relevant if role is DOCTOR
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    doctor_appointments: List["Appointment"] = Relationship(
        back_populates="doctor", 
        sa_relationship_kwargs={"foreign_keys": "Appointment.doctor_id"}
    )
    patient_appointments: List["Appointment"] = Relationship(
        back_populates="patient", 
        sa_relationship_kwargs={"foreign_keys": "Appointment.patient_id"}
    )


class Appointment(SQLModel, table=True):
    """Core scheduling entity linking patients and doctors."""
    __tablename__ = "appointments"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign Keys
    patient_id: int = Field(foreign_key="users.id")
    doctor_id: int = Field(foreign_key="users.id")
    
    date: str  # Format: YYYY-MM-DD
    time: str  # Format: HH:MM
    department: str
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    patient: User = Relationship(
        back_populates="patient_appointments", 
        sa_relationship_kwargs={"foreign_keys": "[Appointment.patient_id]"}
    )
    doctor: User = Relationship(
        back_populates="doctor_appointments", 
        sa_relationship_kwargs={"foreign_keys": "[Appointment.doctor_id]"}
    )
    
    # Links to chat logs and medical records
    symptoms: List["SymptomLog"] = Relationship(back_populates="appointment")
    medical_record: Optional["MedicalRecord"] = Relationship(back_populates="appointment")


class SymptomLog(SQLModel, table=True):
    """Stores the chat history and symptom descriptions from the AI interview."""
    __tablename__ = "symptoms"

    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointments.id")
    
    sender_role: str  # 'patient' or 'ai'
    content: str = Field(sa_column_kwargs={"type_": "TEXT"})
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationship
    appointment: Appointment = Relationship(back_populates="symptoms")


class MedicalRecord(SQLModel, table=True):
    """Stores AI analysis results and the doctor's final diagnosis."""
    __tablename__ = "medical_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointments.id", unique=True)
    
    # AI Generated Content (Helper)
    ai_summary: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    ai_disease_prediction: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    
    # Doctor's Input (Final Decision)
    doctor_diagnosis: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    prescription: Optional[str] = Field(default=None, sa_column_kwargs={"type_": "TEXT"})
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationship
    appointment: Appointment = Relationship(back_populates="medical_record")