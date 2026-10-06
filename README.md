# Эмулятор командной строки ОС (Вариант №16)

GUI-эмулятор языка оболочки UNIX-подобной ОС. Проект выполняется поэтапно,
каждый этап фиксируется отдельным коммитом.

> **Текущий этап: Этап 5 — Дополнительные команды.**
> Реализованы `ls`, `cd`, `cat`, `uname`, `date`, `rmdir`; VFS хранится в
> памяти и изменяется только в памяти.

## 1. Общее описание

Приложение имитирует работу командной строки UNIX-подобной ОС в виде
графического интерфейса (GUI) на Python (`tkinter`). Пользователь вводит
команды в поле ввода, результат выводится в область истории — как в терминале.

Заголовок окна отображает имя VFS: имя файла из параметра `--vfs`, а если
параметр не задан — `vfs`.

### VFS

- Источник VFS — ZIP-архив (`--vfs PATH`). Архив целиком читается в память;
  на диск ничего не распаковывается и не изменяется.
- Архив можно передать как есть или в виде **base64-текста**: файл, не
  начинающийся с `PK`, декодируется из base64. Тестовые VFS в репозитории
  хранятся в base64, поэтому в нём нет бинарных файлов и архивов.
- Двоичные файлы внутри VFS при выводе (`cat`, `vfs-dump`) представляются
  в base64.
- Каталоги, которых нет в архиве явными записями, восстанавливаются по путям
  файлов.
- Ошибки загрузки (файла нет, это каталог, не ZIP/не base64, повреждённый
  архив) выводятся в консоль эмулятора; приложение продолжает работу без VFS.

## 2. Описание всех функций и настроек

### Команды

| Команда | Поведение |
| ------- | --------- |
| `ls [-l] [PATH...]` | содержимое каталогов VFS; без аргументов — текущий каталог |
| `cd [PATH]` | смена текущего каталога; без аргументов — в корень |
| `cat FILE...` | содержимое файлов (двоичные — в base64) |
| `uname [-a] [-s] [-n] [-r] [-v] [-m]` | сведения об (эмулируемой) системе |
| `date [-u] [+FORMAT]` | текущие дата и время |
| `rmdir [-p] [-v] DIR...` | удаление пустых каталогов (только в памяти) |
| `echo [текст]` | выводит переданный текст |
| `vfs-info` | служебная: сводка и все элементы VFS |
| `vfs-dump PATH` | служебная: содержимое файла по пути от корня |
| `exit` | завершает работу эмулятора |

Пути могут быть абсолютными (`/home/user`) и относительными (`docs/archive`),
поддерживаются `.` и `..` (выше корня подняться нельзя). Приглашение
показывает текущий каталог: `~gitflic/source/home/user$`.

**ls**
- Без аргументов — список текущего каталога; с путями — список каждого
  (при нескольких путях перед каждым списком печатается `путь:`).
  Если путь — файл, выводится его имя.
- `-l` — подробный формат: тип (`d` каталог, `-` файл), размер, имя.
- Ошибки: `ls: cannot access 'X': No such file or directory`,
  `ls: invalid option -- 'z'`.

**cd**
- `cd PATH` меняет каталог, `cd` без аргументов возвращает в корень.
- Ошибки: `cd: X: No such file or directory`, `cd: X: Not a directory`,
  `cd: too many arguments`.

**cat**
- Выводит содержимое файлов подряд; текст как есть, двоичные данные в base64.
- Ошибки: `cat: X: No such file or directory`, `cat: X: Is a directory`,
  `cat: missing file operand`.

**uname**
- Без опций — `GitflicOS` (то же, что `-s`). Опции: `-s` имя системы,
  `-n` имя узла, `-r` выпуск, `-v` версия, `-m` архитектура, `-a` всё.
  Опции можно объединять: `uname -mn`. Вывод всегда в порядке s, n, r, v, m.
- Ошибки: `uname: invalid option -- 'x'`, `uname: extra operand 'X'`.

**date**
- Без аргументов: `Mon Oct  5 10:42:34 UTC 2026`. `-u` — время в UTC,
  `+FORMAT` — свой формат (как в `strftime`): `date +%Y-%m-%d`.
- Ошибки: `date: invalid option -- 'x'`, `date: invalid date 'X'`.

**rmdir**
- Удаляет пустые каталоги. Изменение происходит только в памяти — исходный
  ZIP не меняется; `vfs-info`, `ls`, `cd`, `cat` сразу видят результат.
- `-v` — печатать `rmdir: removing directory, 'X'` для каждого удалённого
  каталога; `-p` — удалить также родительские каталоги, пока они пусты
  (`rmdir -p a/b/c` удалит `a/b/c`, `a/b`, `a`). Опции можно объединять: `-pv`.
- Можно указать несколько каталогов; ошибка по одному не мешает остальным.
- Ошибки: `rmdir: failed to remove 'X': No such file or directory`,
  `... Not a directory`, `... Directory not empty`,
  `... Device or resource busy` (корень `/` и текущий каталог удалить нельзя),
  `rmdir: missing operand`, `rmdir: invalid option -- 'x'`.

Прочие ошибки: неизвестная команда — `Command "..." not found`; если VFS не
загружена, команды работы с файлами сообщают `Ошибка: VFS не загружена`.

### Параметры командной строки

| Параметр        | Описание                              |
| --------------- | ------------------------------------- |
| `--vfs PATH`    | путь к ZIP-архиву VFS или его base64  |
| `--script PATH` | путь к стартовому скрипту             |

При запуске все параметры выводятся отладочными строками `[debug] ...` — в
окно эмулятора и в stdout.

### Стартовый скрипт

- Текстовый файл, по одной команде в строке (команды этапов 1–4: `src/start`, `rmdir`: `src/start_rmdir`).
- Комментарии начинаются с `#` (строка целиком или хвост строки); пустые
  строки пропускаются.
- На экране отображаются и ввод (с приглашением), и вывод, с небольшой
  паузой между командами.
- Ошибочная команда выводит сообщение, скрипт продолжает работу. Если скрипт
  не найден — сообщение об ошибке, эмулятор остаётся интерактивным.

### Тестовые VFS (`src/vfs/`, base64-текст)

| Файл            | Назначение                                                 |
| --------------- | ---------------------------------------------------------- |
| `minimal.b64`   | минимальный: один файл                                     |
| `multi.b64`     | несколько файлов, один двоичный                            |
| `deep.b64`      | 3+ уровня вложенности (`home/user/docs/archive/2024/...`)  |
| `rmdir.b64`     | пустые каталоги и цепочки для проверки `rmdir`             |
| `not_a_zip.txt` | некорректный VFS (проверка ошибок)                         |

## 3. Сборка и запуск

Требования: Python 3.9+ (только стандартная библиотека, включая `tkinter`).

```bash
./run.sh                                              # без параметров
./run.sh --vfs src/vfs/deep.b64 --script src/start    # тест команд этапов 1-4
./run.sh --vfs src/vfs/rmdir.b64 --script src/start_rmdir  # тест rmdir
```

Скрипты ОС для проверки параметров и вариантов VFS (папка `scripts/`):

```bash
scripts/test_no_params.sh        # без параметров (окно закрыть вручную)
scripts/test_script.sh           # только --script (VFS нет)
scripts/test_script_missing.sh   # несуществующий скрипт
scripts/test_all_params.sh       # --vfs deep.b64 + src/start
scripts/test_vfs_minimal.sh      # минимальный VFS
scripts/test_vfs_multi.sh        # несколько файлов, двоичный файл
scripts/test_vfs_deep.sh         # 3+ уровня вложенности
scripts/test_vfs_zip.sh          # настоящий ZIP (создаётся временно)
scripts/test_vfs_not_zip.sh      # ошибка: не архив
scripts/test_vfs_missing.sh      # ошибка: файла нет
scripts/test_vfs_dir.sh          # ошибка: передан каталог
scripts/test_rmdir.sh            # rmdir: все режимы и ошибки
```

## 4. Примеры использования

```
$ ./run.sh --vfs src/vfs/deep.b64 --script src/start
[debug] Параметры запуска:
[debug]   --vfs    = src/vfs/deep.b64 (найден)
[debug]   --script = src/start (найден)
[debug] VFS загружена в память: файлов 5, каталогов 8
~gitflic/source$ ls -l
d      - bin
d      - etc
d      - home
d      - tmp
~gitflic/source$ cd /home/user/docs
~gitflic/source/home/user/docs$ ls
archive
report.txt
~gitflic/source/home/user/docs$ cat report.txt
quarterly report
~gitflic/source/home/user/docs$ cat /bin/tool.bin
AAECA//+/YBAIBAI
~gitflic/source/home/user/docs$ cd /etc/app.conf
cd: /etc/app.conf: Not a directory
~gitflic/source/home/user/docs$ cat nofile.txt
cat: nofile.txt: No such file or directory
~gitflic/source/home/user/docs$ uname -a
GitflicOS gitflic 1.0 #1 Emulated x86_64
~gitflic/source/home/user/docs$ date +%Y-%m-%d
2026-10-05
~gitflic/source/home/user/docs$ exit
```

Все режимы команд и ошибки собраны в стартовых скриптах `src/start` и
`src/start_rmdir`. Пример `rmdir`:

```
$ ./run.sh --vfs src/vfs/rmdir.b64 --script src/start_rmdir
~gitflic/source$ rmdir -pv chain/one
rmdir: removing directory, 'chain/one'
rmdir: removing directory, 'chain'
~gitflic/source$ rmdir -pv mixed/sub
rmdir: removing directory, 'mixed/sub'
rmdir: failed to remove 'mixed': Directory not empty
~gitflic/source$ rmdir full
rmdir: failed to remove 'full': Directory not empty
```

## Структура репозитория

```
.
├── src/
│   ├── vfs/        # тестовые VFS (base64-текст)
│   ├── main.py     # эмулятор
│   ├── start       # стартовый скрипт (все команды этапов 1-4)
│   └── start_rmdir # стартовый скрипт для rmdir (этап 5)
├── scripts/        # скрипты ОС для проверки параметров и VFS
├── tests/
├── .gitignore
├── README.md
└── run.sh
```
