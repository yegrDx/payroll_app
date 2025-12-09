import tkinter as tk
from tkinter import ttk

from ui_accountant import AccountantLogin
from ui_worker import WorkerLogin

class RoleChoice(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Вход")
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=16)
        frm.grid(row=0, column=0)

        ttk.Label(frm, text="Кто заходит в систему?").grid(row=0, column=0, columnspan=2, pady=(0, 10))

        ttk.Button(frm, text="Бухгалтер", width=18, command=self.open_accountant)\
            .grid(row=1, column=0, padx=6)
        ttk.Button(frm, text="Работник", width=18, command=self.open_worker)\
            .grid(row=1, column=1, padx=6)

    def open_accountant(self):
        self.destroy()
        AccountantLogin().mainloop()

    def open_worker(self):
        self.destroy()
        WorkerLogin().mainloop()
