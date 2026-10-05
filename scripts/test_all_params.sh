#!/usr/bin/env bash
# Оба параметра: полный стартовый скрипт на deep.zip
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/deep.zip" --script "$ROOT/src/start"
