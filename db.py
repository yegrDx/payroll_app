import sqlite3
from config import DB_NAME

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS accountants (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            position TEXT NOT NULL,
            salary REAL NOT NULL CHECK(salary >= 0),
            marital_status TEXT,
            children_count INTEGER DEFAULT 0 CHECK(children_count >= 0),
            password TEXT NOT NULL DEFAULT '1234'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sick_leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            date_start TEXT NOT NULL,
            date_end TEXT NOT NULL,
            period_year INTEGER NOT NULL,
            period_month INTEGER NOT NULL,
            created_by_accountant TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(created_by_accountant) REFERENCES accountants(login)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS allowances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            allowance_type TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            period_year INTEGER NOT NULL,
            period_month INTEGER NOT NULL,
            created_by_accountant TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(created_by_accountant) REFERENCES accountants(login)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS personal_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            new_value TEXT NOT NULL,
            request_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            processed_by TEXT,
            processed_at TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(processed_by) REFERENCES accountants(login)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS financial_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            worker_id INTEGER NOT NULL,
            period_year INTEGER NOT NULL,
            period_month INTEGER NOT NULL,
            accountant_login TEXT NOT NULL,
            action_time TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY(accountant_login) REFERENCES accountants(login)
        )
        """)

        # тестовый бухгалтер
        cur.execute("SELECT COUNT(*) FROM accountants")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO accountants(login, password) VALUES(?, ?)", ("admin", "admin"))

        conn.commit()
