from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    referral_code = Column(String, unique=True, index=True)
    referred_by = Column(String, nullable=True)
    points = Column(Integer, default=0)
    referrals_count = Column(Integer, default=0)
    last_checkin = Column(DateTime, nullable=True)
    entered_draw = Column(Boolean, default=False)
    draw_ticket = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class UserTask(Base):
    __tablename__ = "user_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    task_id = Column(Integer, nullable=False)
    completed_at = Column(DateTime, server_default=func.now())

class DailyLog(Base):
    __tablename__ = "daily_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    date = Column(String, nullable=False)
    tasks_completed = Column(Integer, default=0)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    method = Column(String, nullable=False)
    account = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())
