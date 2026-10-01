import argparse
import os
import sys
import tkinter as tk
from tkinter import scrolledtext


# --- Этап 2: конфигурация ---------------------------------------------------

DEFAULT_VFS_NAME = "vfs"
STEP_DELAY_MS = 400  # пауза между строками стартового скрипта


def parse_args(argv=None):
    """Параметры командной строки: путь к VFS и путь к стартовому скрипту."""
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="GUI-эмулятор командной строки UNIX-подобной ОС.",
    )
    parser.add_argument("--vfs", metavar="PATH",
                        help="путь к физическому расположению VFS")
    parser.add_argument("--script", metavar="PATH",
                        help="путь к стартовому скрипту")
    return parser.parse_args(argv)


def vfs_name(vfs_path):
    """Имя VFS для заголовка окна."""
    if not vfs_path:
        return DEFAULT_VFS_NAME
    return os.path.basename(os.path.normpath(vfs_path)) or DEFAULT_VFS_NAME


def format_debug(vfs_path, script_path):
    """Отладочный вывод всех заданных параметров."""
    def state(path):
        if path is None:
            return "не задан"
        return f"{path} ({'найден' if os.path.exists(path) else 'НЕ НАЙДЕН'})"

    return [
        "[debug] Параметры запуска:",
        f"[debug]   --vfs    = {state(vfs_path)}",
        f"[debug]   --script = {state(script_path)}",
    ]


def load_script(path):
    """Прочитать стартовый скрипт: список команд без комментариев (#) и
    пустых строк. Бросает OSError, если файл недоступен."""
    commands = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                commands.append(line)
    return commands


# ----------------------------------------------------------------------------


class GitflicShellGUI:
    def __init__(self, root, vfs_path=None, script_path=None):
        self.root = root
        self.script_commands = []  # Этап 2

        # Этап 2: имя VFS в заголовке окна
        root.title(f"Эмулятор - VFS: {vfs_name(vfs_path)}")

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

        # Этап 2: отладочный вывод параметров и запуск стартового скрипта
        for line in format_debug(vfs_path, script_path):
            print(line, flush=True)
            self.print_line(line)
        if script_path:
            self.start_script(script_path)

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

    # --- Этап 2: стартовый скрипт ---

    def start_script(self, path):
        try:
            self.script_commands = load_script(path)
        except OSError as e:
            self.print_line(
                f"Ошибка: не удалось прочитать скрипт '{path}': {e.strerror}"
            )
            return
        self.root.after(STEP_DELAY_MS, self.script_step)

    def script_step(self):
        """Выполнить следующую команду скрипта через обычный on_enter,
        поэтому на экране видны и ввод, и вывод."""
        if not self.script_commands:
            return
        command = self.script_commands.pop(0)
        self.entry.insert(0, command)
        self.on_enter()
        if command.split()[0] == "exit":
            return
        self.root.after(STEP_DELAY_MS, self.script_step)


if __name__ == "__main__":
    args = parse_args()
    root = tk.Tk()
    app = GitflicShellGUI(root, args.vfs, args.script)
    root.mainloop()
