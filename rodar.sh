#!/usr/bin/env bash
cd "$(dirname "$0")"
if command -v python3 &>/dev/null; then
    python3 rodar.py "$@"
elif command -v python &>/dev/null; then
    python rodar.py "$@"
else
    echo "Python não foi encontrado no sistema. Por favor instale o Python 3."
    exit 1
fi
