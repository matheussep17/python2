import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import connect, init_db

app = FastAPI(title="Igreja SaaS API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
init_db()
TOKENS = {}

def hashed(value):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(value.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"

def valid_password(value, encoded):
    try:
        salt, expected = encoded.split("$", 1)
        actual = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False

def auth(authorization):
    token = (authorization or "").removeprefix("Bearer ").strip()
    session = TOKENS.get(token)
    if not session:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    return session

def item(row):
    return dict(row) if row else None

class Login(BaseModel):
    tenant_id: str
    email: str
    password: str

class Member(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class Event(BaseModel):
    title: str
    starts_at: str
    ends_at: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

class Account(BaseModel):
    name: str
    opening_balance_cents: int = 0

class Category(BaseModel):
    name: str
    kind: str

class Transaction(BaseModel):
    account_id: int
    category_id: int
    kind: str
    amount: float
    description: str
    occurred_on: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/auth/login")
def login(payload: Login):
    db = connect()
    user = db.execute("SELECT * FROM users WHERE church_id=? AND lower(email)=lower(?)", (payload.tenant_id, payload.email.strip())).fetchone()
    db.close()
    if not user or not valid_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "ID da igreja, e-mail ou senha inválidos.")
    token = secrets.token_urlsafe(32)
    TOKENS[token] = {"user_id": user["id"], "church_id": user["church_id"], "email": user["email"], "role": user["role"]}
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/v1/auth/me")
def me(authorization: Optional[str] = Header(None)):
    return auth(authorization)

@app.post("/api/v1/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    TOKENS.pop(token, None)
    return {"ok": True}

@app.get("/api/v1/members")
def list_members(authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect()
    rows = db.execute("SELECT * FROM members WHERE church_id=? AND active=1 ORDER BY full_name", (session["church_id"],)).fetchall(); db.close()
    return [item(row) for row in rows]

@app.post("/api/v1/members")
def create_member(payload: Member, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect()
    cur = db.execute("INSERT INTO members(church_id,full_name,email,phone) VALUES(?,?,?,?)", (session["church_id"], payload.full_name, payload.email, payload.phone)); db.commit()
    row = db.execute("SELECT * FROM members WHERE id=?", (cur.lastrowid,)).fetchone(); db.close(); return item(row)

@app.patch("/api/v1/members/{member_id}")
def update_member(member_id: int, payload: Member, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); db.execute("UPDATE members SET full_name=?,email=?,phone=? WHERE id=? AND church_id=?", (payload.full_name, payload.email, payload.phone, member_id, session["church_id"])); db.commit(); row = db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone(); db.close(); return item(row)

@app.delete("/api/v1/members/{member_id}")
def delete_member(member_id: int, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); db.execute("UPDATE members SET active=0 WHERE id=? AND church_id=?", (member_id, session["church_id"])); db.commit(); db.close(); return {"ok": True}

@app.get("/api/v1/events")
def list_events(authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); rows = db.execute("SELECT * FROM events WHERE church_id=? ORDER BY starts_at", (session["church_id"],)).fetchall(); db.close(); return [item(row) for row in rows]

@app.post("/api/v1/events")
def create_event(payload: Event, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); cur = db.execute("INSERT INTO events(church_id,title,starts_at,ends_at,location,description) VALUES(?,?,?,?,?,?)", (session["church_id"], payload.title, payload.starts_at, payload.ends_at, payload.location, payload.description)); db.commit(); row = db.execute("SELECT * FROM events WHERE id=?", (cur.lastrowid,)).fetchone(); db.close(); return item(row)

@app.delete("/api/v1/events/{event_id}")
def delete_event(event_id: int, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); db.execute("UPDATE events SET status='cancelled' WHERE id=? AND church_id=?", (event_id, session["church_id"])); db.commit(); db.close(); return {"ok": True}

@app.get("/api/v1/finance/accounts")
def list_accounts(authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); rows = db.execute("SELECT * FROM accounts WHERE church_id=?", (session["church_id"],)).fetchall(); db.close(); return [item(row) | {"balance_cents": row["opening_balance_cents"], "income_cents": 0, "expense_cents": 0} for row in rows]

@app.post("/api/v1/finance/accounts")
def create_account(payload: Account, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); cur = db.execute("INSERT INTO accounts(church_id,name,opening_balance_cents) VALUES(?,?,?)", (session["church_id"], payload.name, payload.opening_balance_cents)); db.commit(); row = db.execute("SELECT * FROM accounts WHERE id=?", (cur.lastrowid,)).fetchone(); db.close(); return item(row) | {"balance_cents": row["opening_balance_cents"], "income_cents": 0, "expense_cents": 0}

@app.get("/api/v1/finance/categories")
def list_categories(authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); rows = db.execute("SELECT * FROM categories WHERE church_id=?", (session["church_id"],)).fetchall(); db.close(); return [item(row) for row in rows]

@app.post("/api/v1/finance/categories")
def create_category(payload: Category, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); cur = db.execute("INSERT INTO categories(church_id,name,kind) VALUES(?,?,?)", (session["church_id"], payload.name, payload.kind)); db.commit(); row = db.execute("SELECT * FROM categories WHERE id=?", (cur.lastrowid,)).fetchone(); db.close(); return item(row)

@app.get("/api/v1/finance/transactions")
def list_transactions(period: str = Query(...), authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); rows = db.execute("SELECT * FROM transactions WHERE church_id=? AND substr(occurred_on,1,7)=? ORDER BY occurred_on DESC,id DESC", (session["church_id"], period)).fetchall(); db.close(); return [item(row) for row in rows]

@app.post("/api/v1/finance/transactions")
def create_transaction(payload: Transaction, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); cents = round(payload.amount * 100); cur = db.execute("INSERT INTO transactions(church_id,account_id,category_id,kind,amount_cents,description,occurred_on) VALUES(?,?,?,?,?,?,?)", (session["church_id"], payload.account_id, payload.category_id, payload.kind, cents, payload.description, payload.occurred_on)); db.commit(); row = db.execute("SELECT * FROM transactions WHERE id=?", (cur.lastrowid,)).fetchone(); db.close(); return item(row)

@app.get("/api/v1/finance/summary")
def finance_summary(period: str = Query(...), authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); rows = db.execute("SELECT kind,SUM(amount_cents) total FROM transactions WHERE church_id=? AND substr(occurred_on,1,7)=? GROUP BY kind", (session["church_id"], period)).fetchall(); accounts = db.execute("SELECT * FROM accounts WHERE church_id=?", (session["church_id"],)).fetchall(); db.close()
    income = next((row["total"] or 0 for row in rows if row["kind"] == "income"), 0); expense = next((row["total"] or 0 for row in rows if row["kind"] == "expense"), 0)
    return {"income_cents": income, "expense_cents": expense, "net_cents": income - expense, "accounts": [item(row) | {"balance_cents": row["opening_balance_cents"], "income_cents": 0, "expense_cents": 0} for row in accounts]}

@app.post("/api/v1/finance/periods/{period}/close")
def close_period(period: str, authorization: Optional[str] = Header(None)):
    session = auth(authorization); db = connect(); db.execute("INSERT OR IGNORE INTO closed_periods VALUES(?,?)", (session["church_id"], period)); db.commit(); db.close(); return {"ok": True}
