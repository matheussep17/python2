import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get('IGREJA_SAAS_DB', Path(__file__).parent / 'data' / 'saas.db'))

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS churches (id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, email TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'owner', UNIQUE(church_id,email));
        CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, full_name TEXT NOT NULL, email TEXT, phone TEXT, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, title TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT, location TEXT, description TEXT, status TEXT NOT NULL DEFAULT 'scheduled');
        CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, name TEXT NOT NULL, opening_balance_cents INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, church_id TEXT NOT NULL, account_id INTEGER NOT NULL, category_id INTEGER NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, description TEXT NOT NULL, occurred_on TEXT NOT NULL, reversal_of INTEGER);
        CREATE TABLE IF NOT EXISTS closed_periods (church_id TEXT NOT NULL, period TEXT NOT NULL, PRIMARY KEY(church_id,period));
        ''')
