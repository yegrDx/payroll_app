from db import get_conn

def auth_accountant(login, password):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT login FROM accountants WHERE login=? AND password=?", (login, password))
        row = cur.fetchone()
        return row[0] if row else None

def auth_worker(tab_number, password):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM workers WHERE tab_number=? AND password=?", (tab_number, password))
        row = cur.fetchone()
        return row[0] if row else None
