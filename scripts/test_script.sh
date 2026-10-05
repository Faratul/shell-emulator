#!/usr/bin/env bash
# Только --script (VFS не задана: vfs-команды сообщают об ошибке)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py" --script "$ROOT/src/start"
