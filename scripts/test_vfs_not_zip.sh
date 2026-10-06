#!/usr/bin/env bash
# VFS: файл не является архивом (ошибка)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/not_a_zip.txt" --script "$TMP"
rm -f "$TMP"
