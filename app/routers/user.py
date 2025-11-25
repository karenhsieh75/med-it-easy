from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from ..database import get_session
from ..models import User, UserRole

router = APIRouter(prefix="/api/users", tags=["使用者管理"])


# Create input
class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: UserRole = UserRole.PATIENT  # 預設為病患
    department: Optional[str] = None

# Login input
class UserLogin(BaseModel):
    username: str
    password: str

# Response
class UserPublic(BaseModel):
    id: int
    username: str
    full_name: str
    role: UserRole
    department: Optional[str] = None


@router.post("/register", response_model=UserPublic)
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    
    # 檢查帳號是否重複
    existing_user = session.exec(select(User).where(User.username == user_data.username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="此帳號已被註冊")

    # 醫生必須要有科別
    if user_data.role == UserRole.DOCTOR and not user_data.department:
        raise HTTPException(status_code=400, detail="註冊醫師帳號必須填寫科別 (department)")

    new_user = User(
        username=user_data.username,
        password_hash=user_data.password,
        full_name=user_data.full_name,
        role=user_data.role,            
        department=user_data.department
    )
    
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


@router.post("/login", response_model=UserPublic)
def login(login_data: UserLogin, session: Session = Depends(get_session)):

    user = session.exec(select(User).where(User.username == login_data.username)).first()
    
    if not user or user.password_hash != login_data.password:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    
    return user


@router.get("/doctors", response_model=List[UserPublic])
def get_doctors(session: Session = Depends(get_session)):
    doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
    return doctors


@router.get("/departments", response_model=List[str])
def get_departments(session: Session = Depends(get_session)):
    
    # 從醫生資料中撈出所有不重複的 department
    doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
    
    # 使用 set 來過濾重複的科別，並排除 None
    departments = list({doc.department for doc in doctors if doc.department})
    return departments


@router.delete("/{user_id}")
def delete_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="找不到此使用者")
        
    session.delete(user)
    session.commit()
    return {"ok": True, "message": f"使用者 {user.full_name} 已刪除"}