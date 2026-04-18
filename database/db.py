import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "aens.db"   # ✅ always use this file only

def get_connection():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Run schema.sql against the SAME aens.db"""
    conn = get_connection()
    cur = conn.cursor()

    schema_path = BASE_DIR / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        cur.executescript(f.read())

    conn.commit()
    conn.close()
