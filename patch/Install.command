#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
python3 ./install.py check
python3 ./install.py install
read -r 'reply?Нажмите Enter, чтобы закрыть окно.'
