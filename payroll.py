from datetime import date, datetime
import calendar

from config import TAX_RATE, ALLOWANCE_TYPES
from db import get_conn

# -------- time / date helpers --------

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()

def month_bounds(year: int, month: int):
    days = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, days)
    return start, end, days

def overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if start > end:
        return 0
    return (end - start).days + 1

# -------- workers --------

def fetch_workers():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tab_number, full_name, position, salary, 
                   COALESCE(marital_status,''), COALESCE(children_count,0)
            FROM workers
            ORDER BY full_name
        """)
        return cur.fetchall()

def fetch_worker(worker_id):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tab_number, full_name, position, salary, 
                   COALESCE(marital_status,''), COALESCE(children_count,0)
            FROM workers WHERE id=?
        """, (worker_id,))
        return cur.fetchone()

def insert_worker(tab, name, pos, salary, marital, children, password="1234"):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO workers(tab_number, full_name, position, salary, marital_status, children_count, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tab, name, pos, salary, marital, children, password))
        conn.commit()

def update_worker_field(worker_id, field_name, new_value):
    allowed = {"full_name", "position", "marital_status", "children_count"}
    if field_name not in allowed:
        raise ValueError("Недопустимое поле для изменения.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE workers SET {field_name}=? WHERE id=?", (new_value, worker_id))
        conn.commit()

# -------- personal change requests --------

def create_personal_request(worker_id, field_name, new_value):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO personal_change_requests(worker_id, field_name, new_value, request_date)
            VALUES (?, ?, ?, ?)
        """, (worker_id, field_name, str(new_value), now_iso()))
        conn.commit()

def fetch_pending_requests():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT r.id, w.full_name, w.tab_number, r.field_name, r.new_value, r.request_date
            FROM personal_change_requests r
            JOIN workers w ON w.id = r.worker_id
            WHERE r.status = 'PENDING'
            ORDER BY r.request_date
        """)
        return cur.fetchall()

def approve_request(req_id, accountant_login):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT worker_id, field_name, new_value 
            FROM personal_change_requests
            WHERE id=? AND status='PENDING'
        """, (req_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Запрос не найден или уже обработан.")
        worker_id, field_name, new_value = row

        if field_name == "children_count":
            new_value = int(new_value)

        update_worker_field(worker_id, field_name, new_value)

        cur.execute("""
            UPDATE personal_change_requests
            SET status='APPROVED', processed_by=?, processed_at=?
            WHERE id=?
        """, (accountant_login, now_iso(), req_id))

        conn.commit()

def reject_request(req_id, accountant_login):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE personal_change_requests
            SET status='REJECTED', processed_by=?, processed_at=?
            WHERE id=? AND status='PENDING'
        """, (accountant_login, now_iso(), req_id))
        if cur.rowcount == 0:
            raise ValueError("Запрос не найден или уже обработан.")
        conn.commit()

# -------- financial operations + audit --------

def add_sick_leave(worker_id, d_start, d_end, year, month, accountant_login):
    if d_end < d_start:
        raise ValueError("Дата выздоровления раньше даты заболевания.")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sick_leaves(worker_id, date_start, date_end, period_year, period_month, 
                                    created_by_accountant, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (worker_id, d_start.isoformat(), d_end.isoformat(), year, month, accountant_login, now_iso()))
        sick_id = cur.lastrowid

        cur.execute("""
            INSERT INTO financial_audit(action_type, entity_id, worker_id, period_year, period_month,
                                        accountant_login, action_time, details)
            VALUES ('ADD_SICK', ?, ?, ?, ?, ?, ?, ?)
        """, (sick_id, worker_id, year, month, accountant_login, now_iso(),
              f"{d_start.isoformat()}..{d_end.isoformat()}"))

        conn.commit()

def add_allowance(worker_id, a_type, amount, year, month, accountant_login):
    if a_type not in ALLOWANCE_TYPES:
        raise ValueError("Неизвестный тип надбавки.")
    if amount < 0:
        raise ValueError("Сумма не может быть отрицательной.")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO allowances(worker_id, allowance_type, amount, period_year, period_month, 
                                   created_by_accountant, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (worker_id, a_type, amount, year, month, accountant_login, now_iso()))
        allow_id = cur.lastrowid

        cur.execute("""
            INSERT INTO financial_audit(action_type, entity_id, worker_id, period_year, period_month,
                                        accountant_login, action_time, details)
            VALUES ('ADD_ALLOW', ?, ?, ?, ?, ?, ?, ?)
        """, (allow_id, worker_id, year, month, accountant_login, now_iso(),
              f"{a_type}: {amount}"))

        conn.commit()

def sick_days_in_month(worker_id, year, month):
    m_start, m_end, days_in_month = month_bounds(year, month)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT date_start, date_end
            FROM sick_leaves
            WHERE worker_id=? AND period_year=? AND period_month=?
        """, (worker_id, year, month))
        rows = cur.fetchall()

    total = 0
    for ds, de in rows:
        s = parse_date(ds)
        e = parse_date(de)
        total += overlap_days(s, e, m_start, m_end)

    return max(0, min(total, days_in_month))

def allowances_sum(worker_id, year, month):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM allowances
            WHERE worker_id=? AND period_year=? AND period_month=?
        """, (worker_id, year, month))
        return float(cur.fetchone()[0] or 0.0)

# -------- salary calculation --------

def calc_salary_row(worker_row, year, month):
    worker_id, tab, name, pos, salary, marital, children = worker_row
    _, _, days_in_month = month_bounds(year, month)

    sick = sick_days_in_month(worker_id, year, month)
    worked = days_in_month - sick

    base = salary * (worked + 0.5 * sick) / days_in_month
    add = allowances_sum(worker_id, year, month)
    gross = base + add

    tax = gross * TAX_RATE
    net = gross - tax

    return (tab, name, pos, sick,
            round(base, 2), round(add, 2),
            round(gross, 2), round(tax, 2), round(net, 2))
