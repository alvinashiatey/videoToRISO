import customtkinter as ctk
from gui import RisoApp


def main():
    ctk.set_appearance_mode("System")
    app = RisoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
