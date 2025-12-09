import tkinter as tk
from tkinter import ttk, messagebox

from auth import auth_worker
from payroll import fetch_worker, create_personal_request

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

        ttk.Button(frm, text="Войти", command=self.do_login)\
            .grid(row=2, column=0, columnspan=2, pady=(8, 0))

        ttk.Label(frm, text="Пароль по умолчанию: 1234")\
            .grid(row=3, column=0, columnspan=2, pady=(8, 0))

    def do_login(self):
        tab = self.v_tab.get().strip()
        password = self.v_pass.get().strip()
        worker_id = auth_worker(tab, password)
        if not worker_id:
            messagebox.showerror("Ошибка", "Неверный табельный номер или пароль.")
            return
        self.destroy()
        WorkerApp(worker_id).mainloop()


class WorkerApp(tk.Tk):
    def __init__(self, worker_id):
        super().__init__()
        self.worker_id = worker_id
        w = fetch_worker(worker_id)
        self.title(f"Работник: {w[2]}")
        self.geometry("720x420")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        info = ttk.LabelFrame(frm, text="Мои данные", padding=10)
        info.pack(fill="x")

        self.lbl_data = ttk.Label(info, text=self.worker_info_text())
        self.lbl_data.pack(anchor="w")

        req = ttk.LabelFrame(frm, text="Запрос на изменение личных данных", padding=10)
        req.pack(fill="x", pady=(12, 0))

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

            if field_name == "children_count":
                int(new_val)

            create_personal_request(self.worker_id, field_name, new_val)
            self.v_value.set("")
            messagebox.showinfo("Готово", "Запрос отправлен бухгалтеру.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
