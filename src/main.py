"""GUI-эмулятор командной строки UNIX-подобной ОС (вариант 16)."""
import argparse
import base64
import binascii
import datetime
import io
import os
import tkinter as tk
import zipfile
from tkinter import scrolledtext

DEFAULT_VFS_NAME = "vfs"
PROMPT_BASE = "~gitflic/source"
FONT = ("Consolas", 11)
STEP_DELAY_MS = 400
CLOSE_DELAY_MS = 200
BASE64_LINE_WIDTH = 76
ZIP_MAGIC = b"PK"
MAX_CD_ARGS = 1
DUMP_ARGS = 1
ERR_NO_ENTRY = "No such file or directory"
NO_VFS = "Ошибка: VFS не загружена (укажите --vfs PATH)"
UNAME_ORDER = "snrvm"
UNAME_INFO = {
    "s": "GitflicOS",
    "n": "gitflic",
    "r": "1.0",
    "v": "#1 Emulated",
    "m": "x86_64",
}


def parse_args(argv=None):
    """Разобрать параметры командной строки: --vfs и --script."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="GUI-эмулятор командной строки UNIX-подобной ОС.",
    )
    parser.add_argument("--vfs", metavar="PATH",
                        help="путь к ZIP-архиву VFS (или его base64)")
    parser.add_argument("--script", metavar="PATH",
                        help="путь к стартовому скрипту")
    return parser.parse_args(argv)


def vfs_name(vfs_path):
    """Вернуть имя VFS для заголовка окна."""
    if not vfs_path:
        return DEFAULT_VFS_NAME
    return os.path.basename(os.path.normpath(vfs_path)) or DEFAULT_VFS_NAME


def describe_path(path):
    """Описать путь для отладочного вывода: найден он или нет."""
    if path is None:
        return "не задан"
    found = "найден" if os.path.exists(path) else "НЕ НАЙДЕН"
    return f"{path} ({found})"


def format_debug(vfs_path, script_path):
    """Вернуть строки отладочного вывода всех параметров запуска."""
    return [
        "[debug] Параметры запуска:",
        f"[debug]   --vfs    = {describe_path(vfs_path)}",
        f"[debug]   --script = {describe_path(script_path)}",
    ]


def load_script(path):
    """Прочитать стартовый скрипт и вернуть команды без комментариев.

    Комментарии начинаются с '#', пустые строки пропускаются.
    Бросает OSError, если файл недоступен.
    """
    commands = []
    with open(path, encoding="utf-8") as script:
        for line in script:
            line = line.split("#", 1)[0].strip()
            if line:
                commands.append(line)
    return commands


class VFSError(Exception):
    """Ошибка загрузки или чтения VFS."""


def unwrap_container(data):
    """Вернуть байты ZIP: сам архив или раскодированный base64-текст."""
    if data.startswith(ZIP_MAGIC):
        return data
    try:
        return base64.b64decode(b"".join(data.split()), validate=True)
    except (binascii.Error, ValueError):
        raise VFSError("файл не является ZIP-архивом (и не base64)")


def open_archive(data):
    """Открыть ZIP-архив из байтов в памяти."""
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise VFSError("файл не является корректным ZIP-архивом")


def content_lines(data):
    """Представить содержимое файла: текст как есть, иначе в base64."""
    try:
        return data.decode("utf-8").splitlines() or [""]
    except UnicodeDecodeError:
        encoded = base64.b64encode(data).decode("ascii")
        step = BASE64_LINE_WIDTH
        return [encoded[i:i + step] for i in range(0, len(encoded), step)]


class VFS:
    """VFS из ZIP-архива, целиком хранящаяся в памяти.

    files: путь без ведущего '/' -> содержимое (bytes).
    dirs: множество путей каталогов (корень не хранится).
    """

    def __init__(self):
        """Создать пустую VFS."""
        self.files = {}
        self.dirs = set()

    @classmethod
    def from_path(cls, path):
        """Загрузить VFS из файла (ZIP или base64-текст)."""
        try:
            with open(path, "rb") as source:
                data = source.read()
        except OSError as err:
            raise VFSError(f"не удалось открыть '{path}': {err.strerror}")
        return cls.from_bytes(data)

    @classmethod
    def from_bytes(cls, data):
        """Построить VFS из байтов ZIP-архива или его base64."""
        archive = open_archive(unwrap_container(data))
        vfs = cls()
        with archive:
            for info in archive.infolist():
                vfs.add_entry(archive, info)
        return vfs

    def add_entry(self, archive, info):
        """Добавить в VFS запись архива (каталог или файл)."""
        name = info.filename.strip("/")
        if not name:
            return
        if info.is_dir():
            self.add_dir(name)
            return
        try:
            content = archive.read(info)
        except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as err:
            raise VFSError(f"не удалось прочитать '{name}': {err}")
        self.add_file(name, content)

    def add_dir(self, name):
        """Добавить каталог вместе со всеми родительскими."""
        parts = name.split("/")
        for i in range(1, len(parts) + 1):
            self.dirs.add("/".join(parts[:i]))

    def add_file(self, name, content):
        """Добавить файл; недостающие каталоги создаются."""
        if "/" in name:
            self.add_dir(name.rsplit("/", 1)[0])
        self.files[name] = content

    def describe(self):
        """Вернуть сводку и список всех элементов VFS."""
        lines = [f"Файлов: {len(self.files)}, каталогов: {len(self.dirs)}"]
        for path in sorted(self.dirs | set(self.files)):
            if path in self.files:
                data = self.files[path]
                kind = "binary" if is_binary(data) else "text"
                lines.append(f"/{path}  ({kind}, {len(data)} B)")
            else:
                lines.append(f"/{path}/")
        return lines

    def dump(self, path):
        """Вернуть содержимое файла строками (двоичные - в base64)."""
        name = path.strip("/")
        if name in self.files:
            return content_lines(self.files[name])
        if self.is_dir(name):
            raise VFSError(f"'{path}' - каталог")
        raise VFSError(f"'{path}': нет такого файла")

    def resolve(self, cwd, path):
        """Нормализовать путь ('' - корень), учитывая '.' и '..'."""
        parts = [] if path.startswith("/") else cwd.split("/") if cwd else []
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part != "..":
                parts.append(part)
            elif parts:
                parts.pop()
        return "/".join(parts)

    def is_dir(self, name):
        """Проверить, что name - каталог (корень тоже каталог)."""
        return name == "" or name in self.dirs

    def is_file(self, name):
        """Проверить, что name - файл."""
        return name in self.files

    def listdir(self, name):
        """Вернуть отсортированные имена элементов каталога name."""
        result = []
        for path in self.dirs | set(self.files):
            parent, _, base = path.rpartition("/")
            if parent == name:
                result.append(base)
        return sorted(result)

    def remove_dir(self, name):
        """Удалить каталог из памяти; архив на диске не затрагивается."""
        self.dirs.discard(name)


def is_binary(data):
    """Проверить, что данные не являются текстом UTF-8."""
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def split_options(args, allowed, prog):
    """Разделить аргументы на опции и операнды.

    Возвращает (набор опций, список операндов, текст ошибки).
    """
    flags, operands, options_done = set(), [], False
    for arg in args:
        if not options_done and arg == "--":
            options_done = True
        elif not options_done and arg.startswith("-") and arg != "-":
            for char in arg[1:]:
                if char not in allowed:
                    return None, None, f"{prog}: invalid option -- '{char}'"
                flags.add(char)
        else:
            operands.append(arg)
    return flags, operands, None


def ls_entry(vfs, parent, name, long_format):
    """Сформировать строку ls для одного элемента каталога."""
    if not long_format:
        return name
    full = f"{parent}/{name}" if parent else name
    if vfs.is_dir(full):
        return f"d {'-':>6} {name}"
    return f"- {len(vfs.files[full]):>6} {name}"


def ls_classify(vfs, cwd, operands):
    """Разложить операнды ls на ошибки, файлы и каталоги."""
    errors, files, dirs = [], [], []
    for arg in operands:
        target = vfs.resolve(cwd, arg)
        if vfs.is_dir(target):
            dirs.append((arg, target))
        elif vfs.is_file(target):
            files.append(target)
        else:
            errors.append(f"ls: cannot access '{arg}': {ERR_NO_ENTRY}")
    return errors, files, dirs


def ls_sections(vfs, dirs, lines, long_format, headers):
    """Дописать в lines содержимое каталогов (с заголовками при headers)."""
    for arg, target in dirs:
        if lines:
            lines.append("")
        if headers:
            lines.append(f"{arg}:")
        for name in vfs.listdir(target):
            lines.append(ls_entry(vfs, target, name, long_format))
    return lines


def cmd_ls(vfs, cwd, args):
    """ls [-l] [PATH...]: показать содержимое каталогов VFS."""
    if vfs is None:
        return [NO_VFS]
    flags, operands, error = split_options(args, "l", "ls")
    if error:
        return [error]
    long_format = "l" in flags
    operands = operands or ["."]
    errors, files, dirs = ls_classify(vfs, cwd, operands)
    lines = list(errors)
    for target in files:
        parent, _, name = target.rpartition("/")
        lines.append(ls_entry(vfs, parent, name, long_format))
    headers = bool(operands[1:])
    return ls_sections(vfs, dirs, lines, long_format, headers)


def cmd_cd(vfs, cwd, args):
    """cd [PATH]: сменить каталог. Вернуть (новый каталог, вывод)."""
    if vfs is None:
        return cwd, [NO_VFS]
    if len(args) > MAX_CD_ARGS:
        return cwd, ["cd: too many arguments"]
    target = vfs.resolve(cwd, args[0]) if args else ""
    if vfs.is_dir(target):
        return target, []
    if vfs.is_file(target):
        return cwd, [f"cd: {args[0]}: Not a directory"]
    return cwd, [f"cd: {args[0]}: {ERR_NO_ENTRY}"]


def cmd_cat(vfs, cwd, args):
    """cat FILE...: вывести файлы (двоичные - в base64)."""
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
            lines.append(f"cat: {arg}: {ERR_NO_ENTRY}")
    return lines


def uname_flags(args):
    """Разобрать опции uname. Вернуть (набор ключей, текст ошибки)."""
    selected = set()
    for arg in args:
        if not arg.startswith("-") or arg == "-":
            return None, f"uname: extra operand '{arg}'"
        for char in arg[1:]:
            if char == "a":
                selected |= set(UNAME_INFO)
            elif char in UNAME_INFO:
                selected.add(char)
            else:
                return None, f"uname: invalid option -- '{char}'"
    return selected, None


def cmd_uname(args):
    """uname [-a] [-s] [-n] [-r] [-v] [-m]: сведения о системе."""
    selected, error = uname_flags(args)
    if error:
        return [error]
    selected = selected or {"s"}
    return [" ".join(UNAME_INFO[c] for c in UNAME_ORDER if c in selected)]


def date_args(args):
    """Разобрать аргументы date. Вернуть (utc, формат, текст ошибки)."""
    utc, fmt = False, None
    for arg in args:
        if arg == "-u":
            utc = True
        elif arg.startswith("+"):
            fmt = arg[1:]
        elif arg.startswith("-"):
            return utc, fmt, f"date: invalid option -- '{arg.lstrip('-')}'"
        else:
            return utc, fmt, f"date: invalid date '{arg}'"
    return utc, fmt, None


def current_time(utc):
    """Вернуть текущее время (в UTC, если utc=True)."""
    now = datetime.datetime.now().astimezone()
    return now.astimezone(datetime.timezone.utc) if utc else now


def cmd_date(args, now=None):
    """date [-u] [+FORMAT]: показать дату и время."""
    utc, fmt, error = date_args(args)
    if error:
        return [error]
    now = now or current_time(utc)
    if fmt is not None:
        return [now.strftime(fmt)]
    return [f"{now:%a %b} {now.day:2d} {now:%H:%M:%S %Z %Y}"]


def rmdir_one(vfs, cwd, shown):
    """Удалить один пустой каталог. Вернуть текст ошибки или None."""
    target = vfs.resolve(cwd, shown)
    if vfs.is_file(target):
        return "Not a directory"
    if not vfs.is_dir(target):
        return ERR_NO_ENTRY
    if target in ("", cwd):
        return "Device or resource busy"
    if vfs.listdir(target):
        return "Directory not empty"
    vfs.remove_dir(target)
    return None


def rmdir_path(vfs, cwd, arg, parents, verbose):
    """Удалить каталог (с -p и родителей). Вернуть строки вывода."""
    lines = []
    shown = arg.rstrip("/") or "/"
    while shown:
        error = rmdir_one(vfs, cwd, shown)
        if error:
            lines.append(f"rmdir: failed to remove '{shown}': {error}")
            break
        if verbose:
            lines.append(f"rmdir: removing directory, '{shown}'")
        if not parents:
            break
        shown = shown.rpartition("/")[0]
    return lines


def cmd_rmdir(vfs, cwd, args):
    """rmdir [-p] [-v] DIR...: удалить пустые каталоги (в памяти)."""
    if vfs is None:
        return [NO_VFS]
    flags, operands, error = split_options(args, "pv", "rmdir")
    if error:
        return [error]
    if not operands:
        return ["rmdir: missing operand"]
    lines = []
    for arg in operands:
        lines += rmdir_path(vfs, cwd, arg, "p" in flags, "v" in flags)
    return lines


class Session:
    """Состояние оболочки (VFS, текущий каталог) и выполнение команд."""

    def __init__(self, vfs=None):
        """Создать сессию; vfs может быть None (VFS не загружена)."""
        self.vfs = vfs
        self.cwd = ""
        self.running = True
        self.commands = {
            "echo": self.do_echo,
            "exit": self.do_exit,
            "ls": self.do_ls,
            "cd": self.do_cd,
            "cat": self.do_cat,
            "uname": self.do_uname,
            "date": self.do_date,
            "rmdir": self.do_rmdir,
            "vfs-info": self.do_vfs_info,
            "vfs-dump": self.do_vfs_dump,
        }

    @property
    def prompt(self):
        """Приглашение с текущим каталогом."""
        return f"{PROMPT_BASE}/{self.cwd}$" if self.cwd else f"{PROMPT_BASE}$"

    def execute(self, cmd, args):
        """Выполнить команду и вернуть строки вывода."""
        handler = self.commands.get(cmd)
        if handler is None:
            return [f'Command "{cmd}" not found']
        return handler(args)

    def do_echo(self, args):
        """echo: вывести аргументы."""
        return [" ".join(args)]

    def do_exit(self, args):
        """exit: завершить работу эмулятора."""
        self.running = False
        return []

    def do_ls(self, args):
        """ls: список содержимого каталогов."""
        return cmd_ls(self.vfs, self.cwd, args)

    def do_cd(self, args):
        """cd: смена текущего каталога."""
        self.cwd, lines = cmd_cd(self.vfs, self.cwd, args)
        return lines

    def do_cat(self, args):
        """cat: вывод содержимого файлов."""
        return cmd_cat(self.vfs, self.cwd, args)

    def do_uname(self, args):
        """uname: сведения о системе."""
        return cmd_uname(args)

    def do_date(self, args):
        """date: текущие дата и время."""
        return cmd_date(args)

    def do_rmdir(self, args):
        """rmdir: удаление пустых каталогов."""
        return cmd_rmdir(self.vfs, self.cwd, args)

    def do_vfs_info(self, args):
        """vfs-info: сводка и содержимое всей VFS."""
        if self.vfs is None:
            return [NO_VFS]
        return self.vfs.describe()

    def do_vfs_dump(self, args):
        """vfs-dump PATH: содержимое файла по пути от корня."""
        if self.vfs is None:
            return [NO_VFS]
        if len(args) != DUMP_ARGS:
            return ["Использование: vfs-dump PATH"]
        try:
            return self.vfs.dump(args[0])
        except VFSError as err:
            return [f"Ошибка: {err}"]


class GitflicShellGUI:
    """Окно эмулятора: консоль вывода, строка ввода, стартовый скрипт."""

    def __init__(self, root, vfs_path=None, script_path=None):
        """Построить окно, загрузить VFS и запустить стартовый скрипт."""
        self.root = root
        self.session = Session()
        self.script_commands = []
        root.title(f"Эмулятор - VFS: {vfs_name(vfs_path)}")
        self.output = self.build_output()
        self.prompt, self.entry = self.build_input()
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus_set()
        self.startup(vfs_path, script_path)

    def build_output(self):
        """Создать поле вывода (консоль)."""
        output = scrolledtext.ScrolledText(
            self.root,
            bg="black",
            fg="#d0d0d0",
            insertbackground="white",
            font=FONT,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        output.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))
        return output

    def build_input(self):
        """Создать строку ввода: приглашение и поле ввода."""
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, padx=6, pady=6)
        prompt = tk.Label(frame, text=self.session.prompt, font=FONT,
                          fg="#4ec9b0")
        prompt.pack(side=tk.LEFT)
        entry = tk.Entry(frame, font=FONT, bg="#1e1e1e", fg="white",
                         insertbackground="white")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        return prompt, entry

    def startup(self, vfs_path, script_path):
        """Вывести параметры, загрузить VFS и запустить скрипт."""
        for line in format_debug(vfs_path, script_path):
            print(line, flush=True)
            self.print_line(line)
        if vfs_path:
            self.load_vfs(vfs_path)
        if script_path:
            self.start_script(script_path)

    def print_line(self, text=""):
        """Добавить строку в окно вывода."""
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    def update_prompt(self):
        """Обновить приглашение (текущий каталог мог измениться)."""
        self.prompt.config(text=self.session.prompt)

    def on_enter(self, event=None):
        """Обработать ввод: показать команду, выполнить, вывести результат."""
        raw = self.entry.get()
        self.entry.delete(0, tk.END)
        self.print_line(f"{self.session.prompt} {raw}")
        words = raw.split()
        if not words:
            return
        for line in self.session.execute(words[0], words[1:]):
            self.print_line(line)
        self.update_prompt()
        if not self.session.running:
            self.root.after(CLOSE_DELAY_MS, self.root.destroy)

    def load_vfs(self, path):
        """Загрузить VFS в память; ошибку показать в консоли."""
        try:
            self.session.vfs = VFS.from_path(path)
        except VFSError as err:
            self.print_line(f"Ошибка VFS: {err}")
            return
        vfs = self.session.vfs
        msg = (f"[debug] VFS загружена в память: файлов {len(vfs.files)}, "
               f"каталогов {len(vfs.dirs)}")
        print(msg, flush=True)
        self.print_line(msg)

    def start_script(self, path):
        """Прочитать стартовый скрипт и запустить его выполнение."""
        try:
            self.script_commands = load_script(path)
        except OSError as err:
            self.print_line(
                f"Ошибка: не удалось прочитать скрипт '{path}': {err.strerror}"
            )
            return
        self.root.after(STEP_DELAY_MS, self.script_step)

    def script_step(self):
        """Выполнить следующую команду скрипта через обычный on_enter."""
        if not self.script_commands or not self.session.running:
            return
        self.entry.insert(0, self.script_commands.pop(0))
        self.on_enter()
        if self.session.running:
            self.root.after(STEP_DELAY_MS, self.script_step)


def main():
    """Точка входа: разобрать параметры и запустить окно."""
    args = parse_args()
    root = tk.Tk()
    GitflicShellGUI(root, args.vfs, args.script)
    root.mainloop()


if __name__ == "__main__":
    main()
