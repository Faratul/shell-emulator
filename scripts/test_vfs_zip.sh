#!/usr/bin/env bash
# VFS: настоящий ZIP-архив (создаётся во временном файле, в репозитории
# бинарных файлов нет)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="$(mktemp)"
SCRIPT="$(mktemp)"
python3 - "$ARCHIVE" << 'PY'
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("a/b/c/deep.txt", "inside a real zip\n")
PY
printf 'vfs-info\ncat /a/b/c/deep.txt\nexit\n' > "$SCRIPT"
python3 "$ROOT/src/main.py" --vfs "$ARCHIVE" --script "$SCRIPT"
rm -f "$ARCHIVE" "$SCRIPT"
