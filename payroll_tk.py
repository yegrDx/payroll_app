import sqlite3
from datetime import date, datetime
import calendar
import tkinter as tk
from tkinter import ttk, messagebox

DB_NAME = "payroll_roles.db"
TAX_RATE = 0.13
ALLOWANCE_TYPES = ("Премия", "Стаж", "Квалификация")


# -------------------- DB --------------------

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
            tab_number TEXT UNIQUE NOT NULL,   -- табельный номер
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
            status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING/APPROVED/REJECTED
            processed_by TEXT,
            processed_at TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(processed_by) REFERENCES accountants(login)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS financial_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL, -- ADD_SICK / ADD_ALLOW
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


# -------------------- Helpers --------------------

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


# -------------------- Data access --------------------

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
    # ограничим только личные поля
    allowed = {"full_name", "position", "marital_status", "children_count"}
    if field_name not in allowed:
        raise ValueError("Недопустимое поле для изменения.")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE workers SET {field_name}=? WHERE id=?", (new_value, worker_id))
        conn.commit()


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

        # преобразование типов для отдельных полей
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


def calc_salary_row(worker_row, year, month):
    worker_id, tab, name, pos, salary, marital, children = worker_row
    _, _, days_in_month = month_bounds(year, month)

    sick = sick_days_in_month(worker_id, year, month)
    worked = days_in_month - sick

    # Правило 1
    base = salary * (worked + 0.5 * sick) / days_in_month

    add = allowances_sum(worker_id, year, month)
    gross = base + add

    # Правило 2
    tax = gross * TAX_RATE
    net = gross - tax

    return (tab, name, pos, sick,
            round(base, 2), round(add, 2),
            round(gross, 2), round(tax, 2), round(net, 2))


# -------------------- UI: Role choice --------------------

class RoleChoice(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0)

        ttk.Label(frm, text="Кто заходит в систему?").grid(row=0, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(frm, text="Бухгалтер", width=18, command=self.open_accountant_login)\
            .grid(row=1, column=0, padx=6)
        ttk.Button(frm, text="Работник", width=18, command=self.open_worker_login)\
            .grid(row=1, column=1, padx=6)

    def open_accountant_login(self):
        self.destroy()
        AccountantLogin().mainloop()

    def open_worker_login(self):
        self.destroy()
        WorkerLogin().mainloop()


# -------------------- UI: Accountant login --------------------

class AccountantLogin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход бухгалтера")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0)

        self.v_login = tk.StringVar()
        self.v_pass = tk.StringVar()

        ttk.Label(frm, text="Логин").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_login, width=24).grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="Пароль").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_pass, width=24, show="*").grid(row=1, column=1, pady=4)

        ttk.Button(frm, text="Войти", command=self.do_login).grid(row=2, column=0, columnspan=2, pady=(8, 0))

        ttk.Label(frm, text="Тестовый вход: admin / admin").grid(row=3, column=0, columnspan=2, pady=(8, 0))

    def do_login(self):
        login = self.v_login.get().strip()
        password = self.v_pass.get().strip()
        acc = auth_accountant(login, password)
        if not acc:
            messagebox.showerror("Ошибка", "Неверный логин или пароль.")
            return
        self.destroy()
        AccountantApp(acc).mainloop()


# -------------------- UI: Worker login --------------------

class WorkerLogin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход работника")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0)

        self.v_tab = tk.StringVar()
        self.v_pass = tk.StringVar()

        ttk.Label(frm, text="Табельный №").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_tab, width=24).grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="Пароль").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_pass, width=24, show="*").grid(row=1, column=1, pady=4)

        ttk.Button(frm, text="Войти", command=self.do_login).grid(row=2, column=0, columnspan=2, pady=(8, 0))

        ttk.Label(frm, text="Пароль по умолчанию: 1234").grid(row=3, column=0, columnspan=2, pady=(8, 0))

    def do_login(self):
        tab = self.v_tab.get().strip()
        password = self.v_pass.get().strip()
        worker_id = auth_worker(tab, password)
        if not worker_id:
            messagebox.showerror("Ошибка", "Неверный табельный номер или пароль.")
            return
        self.destroy()
        WorkerApp(worker_id).mainloop()


# -------------------- UI: Accountant app --------------------

class AccountantApp(tk.Tk):
    def __init__(self, accountant_login):
        super().__init__()
        self.login = accountant_login
        self.title(f"Бухгалтер: {self.login}")
        self.geometry("980x560")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_workers = ttk.Frame(nb)
        self.tab_fin = ttk.Frame(nb)
        self.tab_requests = ttk.Frame(nb)
        self.tab_report = ttk.Frame(nb)

        nb.add(self.tab_workers, text="Работники")
        nb.add(self.tab_fin, text="Финансовые данные")
        nb.add(self.tab_requests, text="Запросы работников")
        nb.add(self.tab_report, text="Ведомость")

        self.build_workers_tab()
        self.build_fin_tab()
        self.build_requests_tab()
        self.build_report_tab()

        self.refresh_workers()
        self.refresh_requests()

    # ---- workers ----

    def build_workers_tab(self):
        bar = ttk.Frame(self.tab_workers)
        bar.pack(fill="x", padx=10, pady=8)

        ttk.Button(bar, text="Добавить работника", command=self.ui_add_worker).pack(side="left", padx=4)
        ttk.Button(bar, text="Обновить", command=self.refresh_workers).pack(side="left", padx=12)

        cols = ("id", "tab", "name", "pos", "salary", "marital", "children")
        self.w_tree = ttk.Treeview(self.tab_workers, columns=cols, show="headings", height=18)
        self.w_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        heads = [
            ("id", "ID", 50),
            ("tab", "Таб. №", 90),
            ("name", "Ф.И.О.", 240),
            ("pos", "Должность", 160),
            ("salary", "Оклад", 90),
            ("marital", "Сем. полож.", 140),
            ("children", "Дети", 60),
        ]
        for c, t, w in heads:
            self.w_tree.heading(c, text=t)
            self.w_tree.column(c, width=w)

    def refresh_workers(self):
        for i in self.w_tree.get_children():
            self.w_tree.delete(i)
        rows = fetch_workers()
        for r in rows:
            self.w_tree.insert("", "end", values=(
                r[0], r[1], r[2], r[3], f"{r[4]:.2f}", r[5] or "", r[6] or 0
            ))
        self.workers_cache = rows
        self.refresh_fin_worker_cb()
        self.refresh_report_worker_cb()

    def ui_add_worker(self):
        win = tk.Toplevel(self)
        win.title("Добавить работника")
        win.resizable(False, False)

        v_tab = tk.StringVar()
        v_name = tk.StringVar()
        v_pos = tk.StringVar()
        v_sal = tk.StringVar()
        v_mar = tk.StringVar()
        v_ch = tk.StringVar(value="0")

        frm = ttk.Frame(win, padding=10)
        frm.grid(row=0, column=0)

        fields = [
            ("Табельный №", v_tab),
            ("Ф.И.О.", v_name),
            ("Должность", v_pos),
            ("Оклад", v_sal),
            ("Семейное положение", v_mar),
            ("Число детей", v_ch),
        ]
        for i, (lbl, var) in enumerate(fields):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(frm, textvariable=var, width=34).grid(row=i, column=1, pady=3)

        def save():
            try:
                tab = v_tab.get().strip()
                name = v_name.get().strip()
                pos = v_pos.get().strip()
                salary = float(v_sal.get().strip().replace(",", "."))
                marital = v_mar.get().strip()
                children = int(v_ch.get().strip() or "0")

                if not tab or not name or not pos:
                    raise ValueError("Заполните табельный №, Ф.И.О. и должность.")

                insert_worker(tab, name, pos, salary, marital, children)
                win.destroy()
                self.refresh_workers()
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка", "Табельный номер должен быть уникальным.", parent=win)
            except Exception as e:
                messagebox.showerror("Ошибка", str(e), parent=win)

        ttk.Button(frm, text="Сохранить", command=save).grid(row=len(fields), column=0, pady=8)
        ttk.Button(frm, text="Отмена", command=win.destroy).grid(row=len(fields), column=1, pady=8)

        win.grab_set()

    # ---- financial tab ----

    def build_fin_tab(self):
        top = ttk.Frame(self.tab_fin)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="Работник:").pack(side="left")

        self.fin_worker_cb = ttk.Combobox(top, state="readonly", width=50)
        self.fin_worker_cb.pack(side="left", padx=6)

        now = date.today()
        self.fin_year = tk.StringVar(value=str(now.year))
        self.fin_month = tk.StringVar(value=str(now.month))

        ttk.Label(top, text="Год").pack(side="left", padx=(10, 2))
        ttk.Entry(top, textvariable=self.fin_year, width=6).pack(side="left")
        ttk.Label(top, text="Месяц").pack(side="left", padx=(10, 2))
        ttk.Entry(top, textvariable=self.fin_month, width=4).pack(side="left")

        # Блок больничных
        sick_box = ttk.LabelFrame(self.tab_fin, text="Добавить больничный", padding=10)
        sick_box.pack(fill="x", padx=10, pady=6)

        self.v_s1 = tk.StringVar()
        self.v_s2 = tk.StringVar()

        ttk.Label(sick_box, text="Заболел (YYYY-MM-DD)").grid(row=0, column=0, sticky="w")
        ttk.Entry(sick_box, textvariable=self.v_s1, width=16).grid(row=0, column=1, padx=6)

        ttk.Label(sick_box, text="Выздоровел (YYYY-MM-DD)").grid(row=0, column=2, sticky="w")
        ttk.Entry(sick_box, textvariable=self.v_s2, width=16).grid(row=0, column=3, padx=6)

        ttk.Button(sick_box, text="Добавить", command=self.ui_add_sick).grid(row=0, column=4, padx=10)

        # Блок надбавок
        allow_box = ttk.LabelFrame(self.tab_fin, text="Добавить надбавку", padding=10)
        allow_box.pack(fill="x", padx=10, pady=6)

        self.v_atype = tk.StringVar(value=ALLOWANCE_TYPES[0])
        self.v_aamt = tk.StringVar()

        ttk.Label(allow_box, text="Тип").grid(row=0, column=0, sticky="w")
        ttk.Combobox(allow_box, state="readonly", values=ALLOWANCE_TYPES, textvariable=self.v_atype, width=18)\
            .grid(row=0, column=1, padx=6)

        ttk.Label(allow_box, text="Сумма").grid(row=0, column=2, sticky="w")
        ttk.Entry(allow_box, textvariable=self.v_aamt, width=14).grid(row=0, column=3, padx=6)

        ttk.Button(allow_box, text="Добавить", command=self.ui_add_allow).grid(row=0, column=4, padx=10)

        # Небольшая подсказка
        ttk.Label(self.tab_fin, text="Все финансовые изменения автоматически фиксируются в журнале бухгалтера.")\
            .pack(anchor="w", padx=12, pady=(6, 0))

    def fin_selected_worker_id(self):
        key = self.fin_worker_cb.get()
        return self.worker_map.get(key)

    def refresh_fin_worker_cb(self):
        rows = getattr(self, "workers_cache", fetch_workers())
        self.worker_map = {f"{r[2]} (таб. {r[1]})": r[0] for r in rows}
        names = list(self.worker_map.keys())
        self.fin_worker_cb["values"] = names
        if names and self.fin_worker_cb.get() not in names:
            self.fin_worker_cb.set(names[0])
        if not names:
            self.fin_worker_cb.set("")

    def ui_add_sick(self):
        try:
            wid = self.fin_selected_worker_id()
            if not wid:
                raise ValueError("Нет выбранного работника.")
            year = int(self.fin_year.get().strip())
            month = int(self.fin_month.get().strip())

            d1 = parse_date(self.v_s1.get())
            d2 = parse_date(self.v_s2.get())

            add_sick_leave(wid, d1, d2, year, month, self.login)
            self.v_s1.set(""); self.v_s2.set("")
            messagebox.showinfo("Готово", "Больничный добавлен и зафиксирован.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def ui_add_allow(self):
        try:
            wid = self.fin_selected_worker_id()
            if not wid:
                raise ValueError("Нет выбранного работника.")
            year = int(self.fin_year.get().strip())
            month = int(self.fin_month.get().strip())

            a_type = self.v_atype.get()
            amount = float(self.v_aamt.get().strip().replace(",", "."))

            add_allowance(wid, a_type, amount, year, month, self.login)
            self.v_aamt.set("")
            messagebox.showinfo("Готово", "Надбавка добавлена и зафиксирована.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---- requests ----

    def build_requests_tab(self):
        bar = ttk.Frame(self.tab_requests)
        bar.pack(fill="x", padx=10, pady=8)

        ttk.Button(bar, text="Обновить", command=self.refresh_requests).pack(side="left", padx=4)
        ttk.Button(bar, text="Одобрить", command=self.ui_approve_request).pack(side="left", padx=12)
        ttk.Button(bar, text="Отклонить", command=self.ui_reject_request).pack(side="left", padx=4)

        cols = ("id", "name", "tab", "field", "value", "date")
        self.req_tree = ttk.Treeview(self.tab_requests, columns=cols, show="headings", height=18)
        self.req_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        heads = [
            ("id", "ID", 60),
            ("name", "Работник", 220),
            ("tab", "Таб. №", 90),
            ("field", "Поле", 140),
            ("value", "Новое значение", 200),
            ("date", "Дата запроса", 160),
        ]
        for c, t, w in heads:
            self.req_tree.heading(c, text=t)
            self.req_tree.column(c, width=w)

    def refresh_requests(self):
        for i in self.req_tree.get_children():
            self.req_tree.delete(i)
        rows = fetch_pending_requests()
        for r in rows:
            self.req_tree.insert("", "end", values=r)

    def selected_request_id(self):
        sel = self.req_tree.selection()
        if not sel:
            return None
        return int(self.req_tree.item(sel[0], "values")[0])

    def ui_approve_request(self):
        try:
            rid = self.selected_request_id()
            if not rid:
                raise ValueError("Выберите запрос.")
            approve_request(rid, self.login)
            self.refresh_requests()
            self.refresh_workers()
            messagebox.showinfo("Готово", "Запрос одобрен.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def ui_reject_request(self):
        try:
            rid = self.selected_request_id()
            if not rid:
                raise ValueError("Выберите запрос.")
            reject_request(rid, self.login)
            self.refresh_requests()
            messagebox.showinfo("Готово", "Запрос отклонён.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---- report ----

    def build_report_tab(self):
        top = ttk.Frame(self.tab_report)
        top.pack(fill="x", padx=10, pady=8)

        now = date.today()
        self.rep_year = tk.StringVar(value=str(now.year))
        self.rep_month = tk.StringVar(value=str(now.month))

        ttk.Label(top, text="Год").pack(side="left")
        ttk.Entry(top, textvariable=self.rep_year, width=6).pack(side="left", padx=6)
        ttk.Label(top, text="Месяц").pack(side="left")
        ttk.Entry(top, textvariable=self.rep_month, width=4).pack(side="left", padx=6)

        ttk.Button(top, text="Сформировать ведомость", command=self.ui_make_report)\
            .pack(side="left", padx=10)

        cols = ("tab", "name", "pos", "sick", "base", "add", "gross", "tax", "net")
        self.rep_tree = ttk.Treeview(self.tab_report, columns=cols, show="headings", height=18)
        self.rep_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        heads = [
            ("tab", "Таб. №", 90),
            ("name", "Ф.И.О.", 220),
            ("pos", "Должность", 150),
            ("sick", "Бол.", 50),
            ("base", "База", 90),
            ("add", "Надб.", 90),
            ("gross", "Начисл.", 90),
            ("tax", "НДФЛ", 90),
            ("net", "К выдаче", 100),
        ]
        for c, t, w in heads:
            self.rep_tree.heading(c, text=t)
            self.rep_tree.column(c, width=w)

        self.rep_total = ttk.Label(self.tab_report, text="Итого: 0.00 | НДФЛ: 0.00 | К выдаче: 0.00")
        self.rep_total.pack(anchor="e", padx=12, pady=(0, 10))

        # для выбора работника в ведомости не нужен, но оставим общий refresh
        self.report_worker_cb = None

    def refresh_report_worker_cb(self):
        # заглушка для совместимости с refresh_workers
        pass

    def ui_make_report(self):
        try:
            year = int(self.rep_year.get().strip())
            month = int(self.rep_month.get().strip())
            if not (1 <= month <= 12):
                raise ValueError("Месяц 1..12.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
            return

        for i in self.rep_tree.get_children():
            self.rep_tree.delete(i)

        rows = fetch_workers()
        total_g = total_t = total_n = 0.0

        for w in rows:
            tab, name, pos, sick, base, add, gross, tax, net = calc_salary_row(w, year, month)
            total_g += gross
            total_t += tax
            total_n += net

            self.rep_tree.insert("", "end", values=(
                tab, name, pos, sick,
                f"{base:.2f}", f"{add:.2f}",
                f"{gross:.2f}", f"{tax:.2f}", f"{net:.2f}"
            ))

        self.rep_total.config(
            text=f"Итого: {total_g:.2f} | НДФЛ: {total_t:.2f} | К выдаче: {total_n:.2f}"
        )


# -------------------- UI: Worker app --------------------

class WorkerApp(tk.Tk):
    def __init__(self, worker_id):
        super().__init__()
        self.worker_id = worker_id
        w = fetch_worker(worker_id)
        self.title(f"Работник: {w[2]}")

        self.geometry("720x420")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        self.info = ttk.LabelFrame(frm, text="Мои данные", padding=10)
        self.info.pack(fill="x")

        self.lbl_data = ttk.Label(self.info, text=self.worker_info_text())
        self.lbl_data.pack(anchor="w")

        req = ttk.LabelFrame(frm, text="Запрос на изменение личных данных", padding=10)
        req.pack(fill="x", pady=(12, 0))

        self.v_field = tk.StringVar(value="full_name")
        self.v_value = tk.StringVar()

        field_map = {
            "Ф.И.О.": "full_name",
            "Должность": "position",
            "Семейное положение": "marital_status",
            "Число детей": "children_count",
        }

        self.field_display = list(field_map.keys())
        self.field_reverse = field_map

        ttk.Label(req, text="Поле").grid(row=0, column=0, sticky="w")
        self.cb_field = ttk.Combobox(req, state="readonly", values=self.field_display, width=24)
        self.cb_field.grid(row=0, column=1, padx=6)
        self.cb_field.set(self.field_display[0])

        ttk.Label(req, text="Новое значение").grid(row=0, column=2, sticky="w")
        ttk.Entry(req, textvariable=self.v_value, width=28).grid(row=0, column=3, padx=6)

        ttk.Button(req, text="Отправить запрос", command=self.ui_send_request)\
            .grid(row=0, column=4, padx=6)

        ttk.Label(frm, text="Правило: работник может запрашивать изменение только своих личных данных.")\
            .pack(anchor="w", pady=(10, 0))

    def worker_info_text(self):
        w = fetch_worker(self.worker_id)
        if not w:
            return "Данные не найдены."
        _, tab, name, pos, salary, marital, children = w
        return (f"Табельный №: {tab}\n"
                f"Ф.И.О.: {name}\n"
                f"Должность: {pos}\n"
                f"Оклад: {salary:.2f}\n"
                f"Семейное положение: {marital}\n"
                f"Число детей: {children}")

    def ui_send_request(self):
        try:
            disp = self.cb_field.get()
            field_name = self.field_reverse.get(disp)
            if not field_name:
                raise ValueError("Некорректное поле.")

            new_val = self.v_value.get().strip()
            if new_val == "":
                raise ValueError("Введите новое значение.")

            # лёгкая проверка типа
            if field_name == "children_count":
                int(new_val)

            create_personal_request(self.worker_id, field_name, new_val)
            self.v_value.set("")
            messagebox.showinfo("Готово", "Запрос отправлен бухгалтеру.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


# -------------------- Run --------------------

def main():
    init_db()
    RoleChoice().mainloop()


if __name__ == "__main__":
    main()
