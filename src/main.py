import tkinter as tk
from tkinter import scrolledtext


class GitflicShellGUI:
    def __init__(self, root):
        self.root = root

        # Поле вывода (консоль)
        self.output = scrolledtext.ScrolledText(
            root,
            bg="black",
            fg="#d0d0d0",
            insertbackground="white",
            font=("Consolas", 11),
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        # Строка ввода
        input_frame = tk.Frame(root)
        input_frame.pack(fill=tk.X, padx=6, pady=6)

        self.prompt = tk.Label(
            input_frame,
            text="~gitflic/source$",
            font=("Consolas", 11),
            fg="#4ec9b0",
        )
        self.prompt.pack(side=tk.LEFT)

        self.entry = tk.Entry(
            input_frame,
            font=("Consolas", 11),
            bg="#1e1e1e",
            fg="white",
            insertbackground="white",
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus_set()

    def print_line(self, text=""):
        """Добавить строку в окно вывода."""
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    def on_enter(self, event=None):
        raw = self.entry.get()
        self.entry.delete(0, tk.END)

        # Эхо введённой команды с приглашением
        self.print_line(f"~gitflic/source$ {raw}")

        a = raw.split()
        if len(a) == 0:
            return

        cmd = a[0]
        args = a[1:]

        if cmd == "echo":
            self.print_line(" ".join(args))
        elif cmd == "exit":
            self.root.after(200, self.root.destroy)
        elif cmd == "ls":
            self.print_line("ls " + " ".join(args))
        elif cmd == "cd":
            self.print_line("cd " + " ".join(args))
        else:
            self.print_line(f'Command "{cmd}" not found')


if __name__ == "__main__":
    root = tk.Tk()
    app = GitflicShellGUI(root)
    root.mainloop()