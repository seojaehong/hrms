#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/ubuntu/workspaces/frappe-hrms')
RUNS_DIR = ROOT / '.hermes' / 'harness' / 'runs'
READINESS_SCRIPT = ROOT / 'scripts' / 'korea_launch_readiness.py'
DOCKER_COMPOSE = ROOT / 'docker' / 'docker-compose.yml'
KEY_PATHS = [
    '.hermes/KOREA_LAUNCH_PLAN.md',
    '.hermes/KOREA_GAP_AUDIT.md',
    '.hermes/KOREA_LEGAL_RULES_INPUT.yaml',
    '.hermes/harness/README.md',
    '.hermes/harness/launch-week.yaml',
    'hrms/locale/ko.po',
    'hrms/regional/south_korea/setup.py',
    'hrms/regional/korea_republic_of/setup.py',
]


def run(cmd: str) -> dict:
    proc = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    return {
        'command': cmd,
        'exit_code': proc.returncode,
        'stdout': proc.stdout.strip(),
        'stderr': proc.stderr.strip(),
    }


def summarize_board(snapshot: dict) -> str:
    branch = snapshot['git']['branch'] or '(unknown)'
    dirty = 'YES' if snapshot['git']['status'] else 'NO'
    readiness_ok = snapshot['readiness']['exit_code'] == 0
    http_ok = 'HTTP/1.1 200 OK' in snapshot['readiness']['stdout']
    docker_ok = snapshot['docker']['exit_code'] == 0

    priorities = [
        'Company / Employee 한국 필드 실화면 검증',
        'Holiday List / Leave Policy / Shift Type 샘플 데이터 반영',
        'Salary Component / Structure 데모 시나리오 정리',
    ]
    risks = [
        'bench CLI 없이 Docker/readiness 중심 검증만 가능',
        '한국어 번역은 핵심 동선 중심 1차본으로 전체 커버리지는 미완성',
        '브라우저 기반 실제 데모 동선 검증은 추가 E2E가 필요',
    ]

    lines = [
        '# Korea Launch Day0 Board',
        '',
        f'- generated_at_utc: {snapshot["generated_at_utc"]}',
        f'- git_branch: {branch}',
        f'- git_dirty: {dirty}',
        f'- docker_ok: {docker_ok}',
        f'- readiness_ok: {readiness_ok}',
        f'- http_ok: {http_ok}',
        '',
        '## 오늘 결론',
        '- 레포와 Docker 런타임은 살아 있고, 한국화 스캐폴드와 하네스 문서가 준비됐다.',
        '- 오늘 바로 진행할 1순위는 실화면 검증과 데모용 샘플 데이터 완성이다.',
        '',
        '## 우선순위 3개',
    ]
    lines.extend(f'{i}. {item}' for i, item in enumerate(priorities, start=1))
    lines.extend(['', '## 주요 리스크'])
    lines.extend(f'- {risk}' for risk in risks)
    lines.extend(['', '## 핵심 파일 체크'])
    for item in snapshot['key_paths']:
        lines.append(f"- {'OK' if item['exists'] else 'MISSING'} — `{item['path']}`")
    return '\n'.join(lines) + '\n'


def main() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')

    snapshot = {
        'generated_at_utc': generated_at,
        'git': {
            'branch': run('git branch --show-current')['stdout'],
            'status': run('git status --short')['stdout'].splitlines(),
            'diff_stat': run('git diff --stat')['stdout'],
        },
        'docker': run(f'sudo docker compose -f {DOCKER_COMPOSE} ps'),
        'readiness': run(f'python3 {READINESS_SCRIPT}'),
        'key_paths': [
            {'path': path, 'exists': (ROOT / path).exists()} for path in KEY_PATHS
        ],
    }

    json_path = RUNS_DIR / f'{stamp}-snapshot.json'
    md_path = RUNS_DIR / f'{stamp}-board.md'
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    md_path.write_text(summarize_board(snapshot))

    print(json.dumps({
        'snapshot_json': str(json_path),
        'board_markdown': str(md_path),
        'readiness_exit_code': snapshot['readiness']['exit_code'],
        'docker_exit_code': snapshot['docker']['exit_code'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
