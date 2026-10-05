import argparse
import base64
import binascii
import datetime
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

    # --- Этап 4: навигация по VFS ---

    def resolve(self, cwd, path):
        """Нормализованный путь (без ведущего '/', '' = корень).
        Поддерживает абсолютные и относительные пути, '.' и '..'."""
        parts = [] if path.startswith("/") else (cwd.split("/") if cwd else [])
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        return "/".join(parts)

    def is_dir(self, name):
        return name == "" or name in self.dirs

    def is_file(self, name):
        return name in self.files

    def listdir(self, name):
        """Имена элементов каталога name (отсортированы)."""
        result = []
        for path in self.dirs | set(self.files):
            parent, _, base = path.rpartition("/")
            if parent == name:
                result.append(base)
        return sorted(result)

    # --- Этап 5: изменение VFS (только в памяти) ---

    def remove_dir(self, name):
        """Удалить пустой каталог. Архив на диске не затрагивается."""
        self.dirs.discard(name)


# --- Этап 4: команды ls, cd, cat, uname, date ---------------------------------

NO_VFS = "Ошибка: VFS не загружена (укажите --vfs PATH)"


def cmd_ls(vfs, cwd, args):
    """ls [-l] [PATH...]"""
    if vfs is None:
        return [NO_VFS]
    long_format = False
    paths = []
    options_done = False
    for arg in args:
        if not options_done and arg == "--":
            options_done = True
        elif not options_done and arg.startswith("-") and len(arg) > 1:
            for ch in arg[1:]:
                if ch != "l":
                    return [f"ls: invalid option -- '{ch}'"]
            long_format = True
        else:
            paths.append(arg)
    if not paths:
        paths = ["."]

    def entry(parent, name):
        full = f"{parent}/{name}" if parent else name
        if not long_format:
            return name
        if vfs.is_dir(full):
            return f"d {'-':>6} {name}"
        return f"- {len(vfs.files[full]):>6} {name}"

    errors, files, dirs = [], [], []
    for arg in paths:
        target = vfs.resolve(cwd, arg)
        if vfs.is_dir(target):
            dirs.append((arg, target))
        elif vfs.is_file(target):
            files.append(entry(target.rpartition("/")[0],
                               target.rpartition("/")[2]))
        else:
            errors.append(f"ls: cannot access '{arg}': No such file or directory")

    lines = list(errors) + files
    for arg, target in dirs:
        if lines:
            lines.append("")
        if len(paths) > 1:
            lines.append(f"{arg}:")
        lines += [entry(target, name) for name in vfs.listdir(target)]
    return lines


def cmd_cd(vfs, cwd, args):
    """cd [PATH]. Возвращает (новый каталог, строки вывода)."""
    if vfs is None:
        return cwd, [NO_VFS]
    if len(args) > 1:
        return cwd, ["cd: too many arguments"]
    target = vfs.resolve(cwd, args[0]) if args else ""  # cd без аргумента - в корень
    if vfs.is_dir(target):
        return target, []
    if vfs.is_file(target):
        return cwd, [f"cd: {args[0]}: Not a directory"]
    return cwd, [f"cd: {args[0]}: No such file or directory"]


def cmd_cat(vfs, cwd, args):
    """cat FILE... (двоичные файлы выводятся в base64)"""
    if vfs is None:
        return [NO_VFS]
    if not args:
        return ["cat: missing file operand"]
    lines = []
    for arg in args:
        target = vfs.resolve(cwd, arg)
        if vfs.is_file(target):
            lines += vfs.dump(target)
        elif vfs.is_dir(target):
            lines.append(f"cat: {arg}: Is a directory")
        else:
            lines.append(f"cat: {arg}: No such file or directory")
    return lines


UNAME_INFO = {
    "s": "GitflicOS",
    "n": "gitflic",
    "r": "1.0",
    "v": "#1 Emulated",
    "m": "x86_64",
}


def cmd_uname(args):
    """uname [-a] [-s] [-n] [-r] [-v] [-m]"""
    selected = set()
    for arg in args:
        if not arg.startswith("-") or len(arg) == 1:
            return [f"uname: extra operand '{arg}'"]
        for ch in arg[1:]:
            if ch == "a":
                selected |= set(UNAME_INFO)
            elif ch in UNAME_INFO:
                selected.add(ch)
            else:
                return [f"uname: invalid option -- '{ch}'"]
    if not selected:
        selected = {"s"}
    return [" ".join(UNAME_INFO[ch] for ch in "snrvm" if ch in selected)]


def cmd_date(args, now=None):
    """date [-u] [+FORMAT]"""
    utc = False
    fmt = None
    for arg in args:
        if arg == "-u":
            utc = True
        elif arg.startswith("+"):
            fmt = arg[1:]
        elif arg.startswith("-"):
            return [f"date: invalid option -- '{arg.lstrip('-')}'"]
        else:
            return [f"date: invalid date '{arg}'"]
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc if utc
                                    else None).astimezone()
        if utc:
            now = now.astimezone(datetime.timezone.utc)
    if fmt is not None:
        return [now.strftime(fmt)]
    return [f"{now:%a %b} {now.day:2d} {now:%H:%M:%S %Z %Y}"]


# --- Этап 5: команда rmdir ------------------------------------------------------

def cmd_rmdir(vfs, cwd, args):
    """rmdir [-p] [-v] DIR... - удаляет пустые каталоги (только в памяти)"""
    if vfs is None:
        return [NO_VFS]
    parents = verbose = False
    paths = []
    options_done = False
    for arg in args:
        if not options_done and arg == "--":
            options_done = True
        elif not options_done and arg.startswith("-") and len(arg) > 1:
            for ch in arg[1:]:
                if ch == "p":
                    parents = True
                elif ch == "v":
                    verbose = True
                else:
                    return [f"rmdir: invalid option -- '{ch}'"]
        else:
            paths.append(arg)
    if not paths:
        return ["rmdir: missing operand"]

    def try_remove(shown):
        """Удалить каталог; вернуть текст ошибки или None."""
        target = vfs.resolve(cwd, shown)
        if vfs.is_file(target):
            return "Not a directory"
        if not vfs.is_dir(target):
            return "No such file or directory"
        if target == "" or target == cwd:  # корень и текущий каталог
            return "Device or resource busy"
        if vfs.listdir(target):
            return "Directory not empty"
        vfs.remove_dir(target)
        return None

    lines = []
    for arg in paths:
        shown = arg.rstrip("/") or "/"
        while True:
            error = try_remove(shown)
            if error:
                lines.append(f"rmdir: failed to remove '{shown}': {error}")
                break
            if verbose:
                lines.append(f"rmdir: removing directory, '{shown}'")
            if not parents:
                break
            shown = shown.rpartition("/")[0]  # с -p удаляем и родителей
            if not shown:
                break
    return lines


# ----------------------------------------------------------------------------


class GitflicShellGUI:
    def __init__(self, root, vfs_path=None, script_path=None):
        self.root = root
        self.script_commands = []  # Этап 2
        self.vfs = None  # Этап 3
        self.cwd = ""  # Этап 4: текущий каталог VFS ("" - корень)

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
        self.print_line(f"{self.prompt.cget('text')} {raw}")

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
            for line in cmd_ls(self.vfs, self.cwd, args):
                self.print_line(line)
        elif cmd == "cd":
            self.cwd, lines = cmd_cd(self.vfs, self.cwd, args)
            for line in lines:
                self.print_line(line)
            self.update_prompt()
        elif cmd == "cat":
            for line in cmd_cat(self.vfs, self.cwd, args):
                self.print_line(line)
        elif cmd == "uname":
            for line in cmd_uname(args):
                self.print_line(line)
        elif cmd == "date":
            for line in cmd_date(args):
                self.print_line(line)
        elif cmd == "rmdir":
            for line in cmd_rmdir(self.vfs, self.cwd, args):
                self.print_line(line)
        elif cmd in ("vfs-info", "vfs-dump"):  # Этап 3: служебные команды
            for line in self.vfs_command(cmd, args):
                self.print_line(line)
        else:
            self.print_line(f'Command "{cmd}" not found')

    # --- Этап 4: приглашение с текущим каталогом ---

    def update_prompt(self):
        suffix = f"/{self.cwd}" if self.cwd else ""
        self.prompt.config(text=f"~gitflic/source{suffix}$")

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
