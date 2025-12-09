import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import date

from config import ALLOWANCE_TYPES
from auth import auth_accountant
from payroll import (
    fetch_workers, insert_worker,
    fetch_pending_requests, approve_request, reject_request,
    add_sick_leave, add_allowance,
    parse_date, calc_salary_row
)

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

        ttk.Button(frm, text="Войти", command=self.do_login)\
            .grid(row=2, column=0, columnspan=2, pady=(8, 0))

        ttk.Label(frm, text="Тестовый вход: admin / admin")\
            .grid(row=3, column=0, columnspan=2, pady=(8, 0))

    def do_login(self):
        login = self.v_login.get().strip()
        password = self.v_pass.get().strip()
        acc = auth_accountant(login, password)
        if not acc:
            messagebox.showerror("Ошибка", "Неверный логин или пароль.")
            return
        self.destroy()
        AccountantApp(acc).mainloop()


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

    # ---- financial ----

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

        sick_box = ttk.LabelFrame(self.tab_fin, text="Добавить больничный", padding=10)
        sick_box.pack(fill="x", padx=10, pady=6)

        self.v_s1 = tk.StringVar()
        self.v_s2 = tk.StringVar()

        ttk.Label(sick_box, text="Заболел (YYYY-MM-DD)").grid(row=0, column=0, sticky="w")
        ttk.Entry(sick_box, textvariable=self.v_s1, width=16).grid(row=0, column=1, padx=6)

        ttk.Label(sick_box, text="Выздоровел (YYYY-MM-DD)").grid(row=0, column=2, sticky="w")
        ttk.Entry(sick_box, textvariable=self.v_s2, width=16).grid(row=0, column=3, padx=6)

        ttk.Button(sick_box, text="Добавить", command=self.ui_add_sick).grid(row=0, column=4, padx=10)

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

    def refresh_fin_worker_cb(self):
        rows = getattr(self, "workers_cache", fetch_workers())
        self.worker_map = {f"{r[2]} (таб. {r[1]})": r[0] for r in rows}
        names = list(self.worker_map.keys())
        self.fin_worker_cb["values"] = names
        if names and self.fin_worker_cb.get() not in names:
            self.fin_worker_cb.set(names[0])
        if not names:
            self.fin_worker_cb.set("")

    def fin_selected_worker_id(self):
        return self.worker_map.get(self.fin_worker_cb.get())

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
