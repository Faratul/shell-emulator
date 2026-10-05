#!/usr/bin/env bash
# Несуществующий стартовый скрипт: сообщение об ошибке
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py" --script "$ROOT/src/no_such_script"
