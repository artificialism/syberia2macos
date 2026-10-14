#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
python3 - <<'PY'
from pathlib import Path
import subprocess,sys
backups=sorted(p.parent for p in Path('backups').glob('*/backup.json'))
if not backups:raise SystemExit('Резервная копия не найдена.')
subprocess.run([sys.executable,'./install.py','restore','--backup',str(backups[-1])],check=True)
PY
read -r 'reply?Нажмите Enter, чтобы закрыть окно.'
