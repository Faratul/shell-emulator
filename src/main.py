import argparse
import base64
import binascii
import io
import os
import sys
import tkinter as tk
import zipfile
from tkinter import scrolledtext


# --- Этап 2: конфигурация ---------------------------------------------------

DEFAULT_VFS_NAME = "vfs"
STEP_DELAY_MS = 400  # пауза между строками стартового скрипта


def parse_args(argv=None):
    """Параметры командной строки: путь к VFS и путь к стартовому скрипту."""
    parser = argparse.ArgumentParser(
        prog="main.py",
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


# --- Этап 3: виртуальная файловая система (всё хранится в памяти) -----------

class VFSError(Exception):
    """Ошибка загрузки или чтения VFS."""


class VFS:
    """VFS из ZIP-архива. Архив читается в память и никуда не распаковывается.

    files: путь без ведущего '/' -> содержимое (bytes)
    dirs:  множество путей каталогов (корень не хранится)
    """

    def __init__(self):
        self.files = {}
        self.dirs = set()

    # --- загрузка ---

    @classmethod
    def from_path(cls, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise VFSError(f"не удалось открыть '{path}': {e.strerror}")
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls, data):
        """data - ZIP-архив либо его представление в base64 (текст)."""
        if not data.startswith(b"PK"):
            try:
                data = base64.b64decode(b"".join(data.split()), validate=True)
            except (binascii.Error, ValueError):
                raise VFSError("файл не является ZIP-архивом (и не base64)")
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise VFSError("файл не является корректным ZIP-архивом")

        vfs = cls()
        with archive:
            for info in archive.infolist():
                name = info.filename.strip("/")
                if not name:
                    continue
                if info.is_dir():
                    vfs._add_dir(name)
                    continue
                try:
                    content = archive.read(info)
                except (RuntimeError, NotImplementedError,
                        zipfile.BadZipFile) as e:
                    raise VFSError(f"не удалось прочитать '{name}': {e}")
                vfs._add_file(name, content)
        return vfs

    def _add_dir(self, name):
        parts = name.split("/")
        for i in range(1, len(parts) + 1):
            self.dirs.add("/".join(parts[:i]))

    def _add_file(self, name, content):
        if "/" in name:
            self._add_dir(name.rsplit("/", 1)[0])
        self.files[name] = content

    # --- служебные операции ---

    @staticmethod
    def is_text(data):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True

    def describe(self):
        """Список строк: сводка и все элементы VFS."""
        lines = [f"Файлов: {len(self.files)}, каталогов: {len(self.dirs)}"]
        for path in sorted(self.dirs | set(self.files)):
            if path in self.files:
                data = self.files[path]
                kind = "text" if self.is_text(data) else "binary"
                lines.append(f"/{path}  ({kind}, {len(data)} B)")
            else:
                lines.append(f"/{path}/")
        return lines

    def dump(self, path):
        """Содержимое файла: текст как есть, двоичные данные в base64."""
        name = path.strip("/")
        if name in self.files:
            data = self.files[name]
            if self.is_text(data):
                return data.decode("utf-8").splitlines() or [""]
            encoded = base64.b64encode(data).decode("ascii")
            return [encoded[i:i + 76] for i in range(0, len(encoded), 76)]
        if name == "" or name in self.dirs:
            raise VFSError(f"'{path}' - каталог")
        raise VFSError(f"'{path}': нет такого файла")


# ----------------------------------------------------------------------------


class GitflicShellGUI:
    def __init__(self, root, vfs_path=None, script_path=None):
        self.root = root
        self.script_commands = []  # Этап 2
        self.vfs = None  # Этап 3

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
        if vfs_path:  # Этап 3: загрузка VFS в память
            self.load_vfs(vfs_path)
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
        elif cmd in ("vfs-info", "vfs-dump"):  # Этап 3: служебные команды
            for line in self.vfs_command(cmd, args):
                self.print_line(line)
        else:
            self.print_line(f'Command "{cmd}" not found')

    # --- Этап 3: VFS ---

    def load_vfs(self, path):
        try:
            self.vfs = VFS.from_path(path)
        except VFSError as e:
            self.print_line(f"Ошибка VFS: {e}")
            return
        msg = (f"[debug] VFS загружена в память: файлов {len(self.vfs.files)}, "
               f"каталогов {len(self.vfs.dirs)}")
        print(msg, flush=True)
        self.print_line(msg)

    def vfs_command(self, cmd, args):
        """vfs-info - содержимое VFS; vfs-dump PATH - содержимое файла."""
        if self.vfs is None:
            return ["Ошибка: VFS не загружена (укажите --vfs PATH)"]
        if cmd == "vfs-info":
            return self.vfs.describe()
        if len(args) != 1:
            return ["Использование: vfs-dump PATH"]
        try:
            return self.vfs.dump(args[0])
        except VFSError as e:
            return [f"Ошибка: {e}"]

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
