"""Lineup - queue management API (FastAPI + SQLAlchemy + SQLite)."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker

SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me-use-a-long-random-string-in-prod")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./queue.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC


def iso(d: Optional[datetime]) -> Optional[str]:
    return d.isoformat() + "Z" if d else None


# ---------- models ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class Queue(Base):
    __tablename__ = "queues"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=now)


class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False, index=True)
    number = Column(Integer, nullable=False)  # per-queue running number
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="waiting")  # waiting | serving | served | cancelled
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=now)
    called_at = Column(DateTime)
    completed_at = Column(DateTime)


class Event(Base):
    """Snapshot of waiting-queue length, written whenever it changes (feeds the trend chart)."""
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False, index=True)
    ts = Column(DateTime, default=now)
    length = Column(Integer, nullable=False)


Base.metadata.create_all(engine)


# ---------- auth ----------
def hash_pw(pw: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${h}"


def check_pw(pw: str, stored: str) -> bool:
    salt = stored.split("$")[0]
    return hmac.compare_digest(hash_pw(pw, salt), stored)


def make_jwt(uid: int) -> str:
    return jwt.encode({"sub": str(uid), "exp": now() + timedelta(days=7)}, SECRET, algorithm="HS256")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        uid = int(jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired, please sign in again")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Account not found")
    return user


# ---------- schemas ----------
class Creds(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=6, max_length=100)


class NameIn(BaseModel):
    name: str = Field(max_length=60)

    @field_validator("name")
    @classmethod
    def clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class MoveIn(BaseModel):
    direction: str = Field(pattern="^(up|down)$")


# ---------- helpers ----------
def own_queue(db: Session, qid: int, user: User) -> Queue:
    q = db.get(Queue, qid)
    if not q or q.owner_id != user.id:
        raise HTTPException(404, "Queue not found")
    return q


def own_token(db: Session, tid: int, user: User):
    t = db.get(Token, tid)
    if not t:
        raise HTTPException(404, "Token not found")
    return t, own_queue(db, t.queue_id, user)


def waiting_tokens(db: Session, qid: int):
    return db.query(Token).filter_by(queue_id=qid, status="waiting").order_by(Token.position, Token.id).all()


def snapshot(db: Session, qid: int):
    db.add(Event(queue_id=qid, ts=now(), length=len(waiting_tokens(db, qid))))


def tok_out(t: Token) -> dict:
    return {"id": t.id, "number": t.number, "label": f"T-{t.number:03d}", "name": t.name, "status": t.status,
            "created_at": iso(t.created_at), "called_at": iso(t.called_at), "completed_at": iso(t.completed_at)}


def detail(db: Session, q: Queue) -> dict:
    toks = db.query(Token).filter_by(queue_id=q.id).all()
    waiting = sorted((t for t in toks if t.status == "waiting"), key=lambda t: (t.position, t.id))
    serving = sorted((t for t in toks if t.status == "serving"), key=lambda t: t.called_at)
    return {"id": q.id, "name": q.name, "waiting": [tok_out(t) for t in waiting],
            "serving": [tok_out(t) for t in serving],
            "served_count": sum(t.status == "served" for t in toks),
            "cancelled_count": sum(t.status == "cancelled" for t in toks)}


# ---------- app ----------
app = FastAPI(title="Lineup Queue Manager")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.post("/api/auth/register", status_code=201)
def register(c: Creds, db: Session = Depends(get_db)):
    username = c.username.strip().lower()
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(409, "That username is taken")
    u = User(username=username, password_hash=hash_pw(c.password))
    db.add(u)
    db.commit()
    return {"token": make_jwt(u.id), "user": {"id": u.id, "username": u.username}}


@app.post("/api/auth/login")
def login(c: Creds, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=c.username.strip().lower()).first()
    if not u or not check_pw(c.password, u.password_hash):
        raise HTTPException(400, "Incorrect username or password")
    return {"token": make_jwt(u.id), "user": {"id": u.id, "username": u.username}}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username}


@app.get("/api/queues")
def list_queues(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for q in db.query(Queue).filter_by(owner_id=user.id).order_by(Queue.id).all():
        counts = dict(db.query(Token.status, func.count()).filter(Token.queue_id == q.id).group_by(Token.status).all())
        out.append({"id": q.id, "name": q.name, "waiting": counts.get("waiting", 0), "serving": counts.get("serving", 0)})
    return out


@app.post("/api/queues", status_code=201)
def create_queue(b: NameIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.query(Queue).filter(Queue.owner_id == user.id, func.lower(Queue.name) == b.name.lower()).first():
        raise HTTPException(409, "You already have a queue with that name")
    q = Queue(name=b.name, owner_id=user.id)
    db.add(q)
    db.commit()
    snapshot(db, q.id)
    db.commit()
    return {"id": q.id, "name": q.name, "waiting": 0, "serving": 0}


@app.delete("/api/queues/{qid}", status_code=204)
def delete_queue(qid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = own_queue(db, qid, user)
    db.query(Token).filter_by(queue_id=q.id).delete()
    db.query(Event).filter_by(queue_id=q.id).delete()
    db.delete(q)
    db.commit()


@app.get("/api/queues/{qid}")
def get_queue(qid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return detail(db, own_queue(db, qid, user))


@app.post("/api/queues/{qid}/tokens", status_code=201)
def add_token(qid: int, b: NameIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = own_queue(db, qid, user)
    max_num, max_pos = db.query(func.max(Token.number), func.max(Token.position)).filter_by(queue_id=q.id).one()
    db.add(Token(queue_id=q.id, name=b.name, number=(max_num or 0) + 1, position=(max_pos or 0) + 1))
    db.flush()
    snapshot(db, q.id)
    db.commit()
    return detail(db, q)


@app.post("/api/tokens/{tid}/move")
def move_token(tid: int, b: MoveIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t, q = own_token(db, tid, user)
    if t.status != "waiting":
        raise HTTPException(400, "Only waiting tokens can be moved")
    line = waiting_tokens(db, q.id)
    i = next(k for k, x in enumerate(line) if x.id == t.id)
    j = i - 1 if b.direction == "up" else i + 1
    if 0 <= j < len(line):
        other = line[j]
        # positions can tie after edge cases, so renumber the whole line to keep the swap reliable
        line[i], line[j] = other, t
        for k, x in enumerate(line):
            x.position = k + 1
        db.commit()
    return detail(db, q)


@app.post("/api/queues/{qid}/serve-next")
def serve_next(qid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = own_queue(db, qid, user)
    line = waiting_tokens(db, q.id)
    if not line:
        raise HTTPException(400, "No one is waiting in this queue")
    line[0].status, line[0].called_at = "serving", now()
    db.flush()
    snapshot(db, q.id)
    db.commit()
    return detail(db, q)


@app.post("/api/tokens/{tid}/complete")
def complete_token(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t, q = own_token(db, tid, user)
    if t.status != "serving":
        raise HTTPException(400, "Only tokens being served can be completed")
    t.status, t.completed_at = "served", now()
    db.commit()
    return detail(db, q)


@app.post("/api/tokens/{tid}/cancel")
def cancel_token(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t, q = own_token(db, tid, user)
    if t.status != "waiting":
        raise HTTPException(400, "Only waiting tokens can be cancelled")
    t.status, t.completed_at = "cancelled", now()
    db.flush()
    snapshot(db, q.id)
    db.commit()
    return detail(db, q)


@app.get("/api/queues/{qid}/analytics")
def analytics(qid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = own_queue(db, qid, user)
    n = now()
    toks = db.query(Token).filter_by(queue_id=q.id).all()
    called = sorted((t for t in toks if t.called_at), key=lambda t: t.called_at)
    waits = [max(0.0, (t.called_at - t.created_at).total_seconds()) for t in called]
    service = [max(0.0, (t.completed_at - t.called_at).total_seconds())
               for t in toks if t.status == "served" and t.completed_at and t.called_at]
    waiting = [t for t in toks if t.status == "waiting"]
    avg = lambda xs: sum(xs) / len(xs) if xs else 0
    events = db.query(Event).filter_by(queue_id=q.id).order_by(Event.ts, Event.id).all()[-300:]
    trend = [{"t": iso(e.ts), "length": e.length} for e in events] + [{"t": iso(n), "length": len(waiting)}]
    return {
        "summary": {
            "total": len(toks), "waiting": len(waiting),
            "serving": sum(t.status == "serving" for t in toks),
            "served": sum(t.status == "served" for t in toks),
            "cancelled": sum(t.status == "cancelled" for t in toks),
            "avg_wait": avg(waits), "max_wait": max(waits, default=0),
            "avg_service": avg(service),
            "current_avg_wait": avg([max(0.0, (n - t.created_at).total_seconds()) for t in waiting]),
            "peak_length": max((e["length"] for e in trend), default=0),
        },
        "length_trend": trend,
        "wait_history": [{"label": f"T-{t.number:03d}", "wait": w} for t, w in zip(called, waits)][-30:],
    }


_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):  # single-process deploy: serve the built UI too
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
