from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import random
import string

from database import engine, get_db, Base
from models import User, UserTask, DailyLog, Withdrawal
from auth import (
    hash_password, verify_password, create_access_token, get_current_user
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MegaRewards Pro API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TASKS = [
    {"id": 1, "name": "Speed Math Challenge", "points": 65},
    {"id": 2, "name": "Tic-Tac-Toe Arena", "points": 65},
    {"id": 3, "name": "Speed Tap Rush", "points": 65},
    {"id": 4, "name": "Quick User Survey", "points": 60},
    {"id": 5, "name": "Lucky Scratch Card", "points": 65},
    {"id": 6, "name": "Mega Spin Wheel", "points": 65},
    {"id": 7, "name": "Memory Card Match", "points": 65},
    {"id": 8, "name": "Fact or Fiction", "points": 60},
    {"id": 9, "name": "Catch The Star", "points": 65},
    {"id": 10, "name": "Color Match Reflex", "points": 60},
    {"id": 11, "name": "Word Scramble", "points": 65},
    {"id": 12, "name": "Grand Trivia Quiz", "points": 60},
]

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    referral_code: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TaskCompleteRequest(BaseModel):
    task_id: int

class DrawEnterRequest(BaseModel):
    pass

class WithdrawRequest(BaseModel):
    method: str
    account: str
    amount: int

def generate_referral_code() -> str:
    return "MR" + "".join(random.choices(string.digits, k=6))

def generate_ticket() -> str:
    return "LD-" + "".join(random.choices(string.digits, k=6))

@app.get("/")
def root():
    return {"status": "ok", "message": "MegaRewards Pro API is running"}

@app.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    
    code = generate_referral_code()
    while db.query(User).filter(User.referral_code == code).first():
        code = generate_referral_code()
    
    referred_by = None
    if req.referral_code:
        referrer = db.query(User).filter(
            User.referral_code == req.referral_code
        ).first()
        if not referrer:
            raise HTTPException(400, "Invalid referral code")
        if referrer.referrals_count >= 5:
            raise HTTPException(400, "Referral limit reached")
        referrer.referrals_count += 1
        referrer.points += 50
        referred_by = referrer.email
    
    user = User(
        name=req.name,
        email=req.email,
        password_hash=hash_password(req.password),
        referral_code=code,
        referred_by=referred_by,
        points=10
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = create_access_token({"sub": user.email})
    return {
        "success": True,
        "token": token,
        "user": {
            "name": user.name,
            "email": user.email,
            "points": user.points,
            "referral_code": user.referral_code,
        }
    }

@app.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    
    token = create_access_token({"sub": user.email})
    return {
        "success": True,
        "token": token,
        "user": {
            "name": user.name,
            "email": user.email,
            "points": user.points,
            "referral_code": user.referral_code,
            "referrals_count": user.referrals_count,
        }
    }

@app.get("/user/profile")
def profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "success": True,
        "user": {
            "name": user.name,
            "email": user.email,
            "points": user.points,
            "referrals_count": user.referrals_count,
            "referral_code": user.referral_code,
            "entered_draw": user.entered_draw,
            "draw_ticket": user.draw_ticket,
        }
    }

@app.get("/tasks")
def get_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = []
    now = datetime.utcnow()
    for task in TASKS:
        last = db.query(UserTask).filter(
            UserTask.user_id == user.id,
            UserTask.task_id == task["id"]
        ).order_by(UserTask.completed_at.desc()).first()
        
        cooldown = 0
        if last:
            elapsed = (now - last.completed_at).total_seconds()
            cooldown = max(0, int(86400 - elapsed))
        
        result.append({**task, "cooldown_remaining": cooldown})
    return {"success": True, "tasks": result}

@app.post("/task/complete")
def complete_task(
    req: TaskCompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = next((t for t in TASKS if t["id"] == req.task_id), None)
    if not task:
        raise HTTPException(400, "Invalid task")
    
    last = db.query(UserTask).filter(
        UserTask.user_id == user.id,
        UserTask.task_id == req.task_id
    ).order_by(UserTask.completed_at.desc()).first()
    
    if last:
        elapsed = (datetime.utcnow() - last.completed_at).total_seconds()
        if elapsed < 86400:
            raise HTTPException(400, f"Cooldown active. Wait {int(86400 - elapsed)}s")
    
    user.points += task["points"]
    db.add(UserTask(user_id=user.id, task_id=req.task_id))
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user.id,
        DailyLog.date == today
    ).first()
    if log:
        log.tasks_completed += 1
    else:
        db.add(DailyLog(user_id=user.id, date=today, tasks_completed=1))
    
    db.commit()
    return {"success": True, "points_earned": task["points"], "total_points": user.points}

@app.post("/checkin")
def checkin(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.last_checkin:
        elapsed = (datetime.utcnow() - user.last_checkin).total_seconds()
        if elapsed < 86400:
            raise HTTPException(400, f"Wait {int(86400 - elapsed)}s")
    
    user.points += 5
    user.last_checkin = datetime.utcnow()
    db.commit()
    return {"success": True, "points": 5, "total_points": user.points}

@app.post("/draw/enter")
def enter_draw(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_month = datetime.utcnow().strftime("%Y-%m")
    if user.entered_draw and user.draw_ticket:
        raise HTTPException(400, "Already entered this month")
    
    if user.points < 500:
        raise HTTPException(400, f"Need 500 points. You have {user.points}")
    
    user.points -= 500
    user.entered_draw = True
    user.draw_ticket = generate_ticket()
    db.commit()
    return {"success": True, "ticket": user.draw_ticket, "remaining_points": user.points}

@app.post("/withdraw")
def withdraw(
    req: WithdrawRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.method not in ["JazzCash", "EasyPaisa", "Bank Transfer"]:
        raise HTTPException(400, "Invalid method")
    if req.amount < 500:
        raise HTTPException(400, "Minimum withdrawal is 500 points")
    if req.amount > user.points:
        raise HTTPException(400, "Insufficient points")
    
    user.points -= req.amount
    db.add(Withdrawal(
        user_id=user.id,
        method=req.method,
        account=req.account,
        amount=req.amount,
        status="pending"
    ))
    db.commit()
    return {"success": True, "message": "Withdrawal request submitted"}

@app.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    top = db.query(User).order_by(User.points.desc()).limit(10).all()
    return {
        "success": True,
        "leaders": [
            {"rank": i+1, "name": u.name, "points": u.points}
            for i, u in enumerate(top)
        ]
    }

@app.get("/calendar")
def calendar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_month = datetime.utcnow().strftime("%Y-%m")
    logs = db.query(DailyLog).filter(
        DailyLog.user_id == user.id,
        DailyLog.date.like(f"{current_month}%")
    ).all()
    return {
        "success": True,
        "days": {log.date: True for log in logs if log.tasks_completed > 0}
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
