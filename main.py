from db import init_db
from ui_role import RoleChoice

def main():
    init_db()
    RoleChoice().mainloop()

if __name__ == "__main__":
    main()
