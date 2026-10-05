#!/usr/bin/env bash
# VFS: файл не существует (ошибка)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/no_such.zip" --script "$TMP"
rm -f "$TMP"
