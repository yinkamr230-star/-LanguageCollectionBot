import sqlite3
import os
from contextlib import contextmanager
from config import DB_PATH, ADMIN_IDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    language TEXT DEFAULT 'en',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'text',
    options TEXT,
    order_index INTEGER DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Pending',
    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    question_key TEXT NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    FOREIGN KEY(application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    file_type TEXT,
    telegram_file_id TEXT,
    file_name TEXT,
    FOREIGN KEY(application_id) REFERENCES applications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    sent_by INTEGER,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        for admin_id in ADMIN_IDS:
            conn.execute(
                "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (admin_id,)
            )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ---------- Users ----------

def upsert_user(telegram_id, username):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username",
            (telegram_id, username),
        )
        conn.commit()


def set_user_language(telegram_id, lang_code):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET language=? WHERE telegram_id=?", (lang_code, telegram_id)
        )
        conn.commit()


def get_user(telegram_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_language(telegram_id):
    user = get_user(telegram_id)
    return user["language"] if user else "en"


def all_users():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]


# ---------- Admins ----------

def is_admin(telegram_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM admins WHERE telegram_id=?", (telegram_id,)
        ).fetchone()
        return row is not None


# ---------- Projects ----------

def create_project(name, description):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description) VALUES (?, ?)",
            (name, description),
        )
        conn.commit()
        return cur.lastrowid


def add_question(project_id, question_text, question_type="text", options=None, order_index=0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO questions (project_id, question_text, question_type, options, order_index) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, question_text, question_type, options, order_index),
        )
        conn.commit()


def get_projects(active_only=True):
    with get_conn() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM projects WHERE status='active' ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        return dict(row) if row else None


def get_questions(project_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE project_id=? ORDER BY order_index ASC, id ASC",
            (project_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_project(project_id, name=None, description=None, status=None):
    fields, values = [], []
    if name is not None:
        fields.append("name=?")
        values.append(name)
    if description is not None:
        fields.append("description=?")
        values.append(description)
    if status is not None:
        fields.append("status=?")
        values.append(status)
    if not fields:
        return
    values.append(project_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", values)
        conn.commit()


def delete_project(project_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.commit()


def clear_questions(project_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM questions WHERE project_id=?", (project_id,))
        conn.commit()


# ---------- Applications ----------

def create_application(user_telegram_id, project_id):
    user = get_user(user_telegram_id)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO applications (user_id, project_id) VALUES (?, ?)",
            (user["id"], project_id),
        )
        conn.commit()
        return cur.lastrowid


def add_answer(application_id, question_key, question_text, answer_text):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO answers (application_id, question_key, question_text, answer_text) "
            "VALUES (?, ?, ?, ?)",
            (application_id, question_key, question_text, answer_text),
        )
        conn.commit()


def add_file(application_id, file_type, telegram_file_id, file_name):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO files (application_id, file_type, telegram_file_id, file_name) "
            "VALUES (?, ?, ?, ?)",
            (application_id, file_type, telegram_file_id, file_name),
        )
        conn.commit()


def set_application_status(application_id, status):
    with get_conn() as conn:
        conn.execute(
            "UPDATE applications SET status=? WHERE id=?", (status, application_id)
        )
        conn.commit()


def get_application(application_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT a.*, u.telegram_id AS applicant_telegram_id, u.username AS applicant_username, "
            "p.name AS project_name FROM applications a "
            "JOIN users u ON u.id = a.user_id "
            "JOIN projects p ON p.id = a.project_id "
            "WHERE a.id=?",
            (application_id,),
        ).fetchone()
        return dict(row) if row else None


def get_answers(application_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM answers WHERE application_id=? ORDER BY id ASC",
            (application_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_files(application_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE application_id=?", (application_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_applications_for_project(project_id, status=None):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT a.*, u.telegram_id AS applicant_telegram_id, u.username AS applicant_username "
                "FROM applications a JOIN users u ON u.id=a.user_id "
                "WHERE a.project_id=? AND a.status=? ORDER BY a.submitted_at DESC",
                (project_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT a.*, u.telegram_id AS applicant_telegram_id, u.username AS applicant_username "
                "FROM applications a JOIN users u ON u.id=a.user_id "
                "WHERE a.project_id=? ORDER BY a.submitted_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_all_applications():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.*, u.telegram_id AS applicant_telegram_id, u.username AS applicant_username, "
            "p.name AS project_name FROM applications a "
            "JOIN users u ON u.id = a.user_id "
            "JOIN projects p ON p.id = a.project_id "
            "ORDER BY a.submitted_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- Stats ----------

def get_stats():
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        total_projects = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
        total_apps = conn.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"]
        by_status = conn.execute(
            "SELECT status, COUNT(*) c FROM applications GROUP BY status"
        ).fetchall()
        by_project = conn.execute(
            "SELECT p.name, COUNT(a.id) c FROM projects p "
            "LEFT JOIN applications a ON a.project_id = p.id GROUP BY p.id"
        ).fetchall()
        return {
            "total_users": total_users,
            "total_projects": total_projects,
            "total_applications": total_apps,
            "by_status": {r["status"]: r["c"] for r in by_status},
            "by_project": {r["name"]: r["c"] for r in by_project},
        }


# ---------- Broadcasts ----------

def log_broadcast(message, sent_by):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO broadcasts (message, sent_by) VALUES (?, ?)",
            (message, sent_by),
        )
        conn.commit()
