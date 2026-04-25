#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/ubuntu/workspaces/frappe-hrms')
LOCALE_DIR = ROOT / 'hrms' / 'locale'
REGIONAL_DIR = ROOT / 'hrms' / 'regional'
DOCKER_DIR = ROOT / 'docker'


def run(cmd: str, cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def yesno(v: bool) -> str:
    return 'YES' if v else 'NO'


locale_files = sorted(p.name for p in LOCALE_DIR.glob('*.po'))
regional_dirs = sorted(p.name for p in REGIONAL_DIR.iterdir() if p.is_dir())
ko_files = [p for p in locale_files if p.startswith('ko')]

checks: list[tuple[str, bool, str]] = []
checks.append(('ko locale file exists', bool(ko_files), ', '.join(ko_files) or '-'))
checks.append(('regional package for korea exists', any(name in regional_dirs for name in ['south_korea', 'republic_of_korea', 'korea_republic_of']), ', '.join(regional_dirs)))
checks.append(('korea launch plan exists', (ROOT / '.hermes' / 'KOREA_LAUNCH_PLAN.md').exists(), '.hermes/KOREA_LAUNCH_PLAN.md'))
checks.append(('korea gap audit exists', (ROOT / '.hermes' / 'KOREA_GAP_AUDIT.md').exists(), '.hermes/KOREA_GAP_AUDIT.md'))

code, docker_ps = run('sudo docker compose ps', DOCKER_DIR)
checks.append(('docker compose ps ok', code == 0, docker_ps.splitlines()[0] if docker_ps else '-'))

code, curl_out = run('curl -I --max-time 10 http://127.0.0.1:8000')
checks.append(('http 8000 responds', code == 0, curl_out.splitlines()[0] if curl_out else '-'))

print('KOREA LAUNCH READINESS')
print('=' * 80)
for name, ok, detail in checks:
    print(f'- {name}: {yesno(ok)}')
    print(f'  detail: {detail}')

failed_checks = [name for name, ok, _ in checks if not ok]
print('- overall: ' + yesno(not failed_checks))
if failed_checks:
    print('  failed_checks: ' + ', '.join(failed_checks))
    sys.exit(1)
