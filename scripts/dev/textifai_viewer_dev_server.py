from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 8872
PID_PATH_DEFAULT = Path('/tmp/textifai_viewer_8872.pid')
LOG_PATH_DEFAULT = Path('/tmp/textifai_viewer_8872.log')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stable TextifAI viewer dev server launcher.')
    parser.add_argument('--root', required=True, help='Runtime root containing viewer project.')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--project-id-contains', default='')
    parser.add_argument('--kill-existing-textifai-viewer', action='store_true')
    return parser.parse_args()


def read_listener_pid(port: int) -> int | None:
    try:
        proc = subprocess.run(['ss', '-ltnp'], check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return None
    pattern = re.compile(rf':{port}\b')
    pid_pat = re.compile(r'pid=(\d+)')
    for line in proc.stdout.splitlines():
        if not pattern.search(line):
            continue
        match = pid_pat.search(line)
        if match:
            return int(match.group(1))
    return None


def cmdline_for_pid(pid: int) -> str:
    path = Path('/proc') / str(pid) / 'cmdline'
    if not path.exists():
        return ''
    raw = path.read_bytes().replace(b'\x00', b' ').strip()
    return raw.decode('utf-8', errors='replace')


def is_textifai_viewer_process(cmdline: str) -> bool:
    lowered = cmdline.casefold()
    return 'textifai.web_viewer.server' in lowered


def stop_pid(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not Path('/proc', str(pid)).exists():
            return
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)


def wait_http_ok(url: str, timeout_s: float = 8.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def load_json(url: str) -> dict:
    with urlopen(url, timeout=5.0) as response:
        return json.loads(response.read().decode('utf-8'))


def choose_project(projects: list[dict], project_id_contains: str) -> dict:
    if project_id_contains:
        matches = [project for project in projects if project_id_contains in str(project.get('project_id') or '')]
        if not matches:
            raise RuntimeError(f'project_id containing "{project_id_contains}" not found')
        preferred = [project for project in matches if str(project.get('name') or '') == 'viewer_project']
        if preferred:
            return preferred[0]
        preferred_kind = [project for project in matches if str(project.get('kind') or '') == 'system_run']
        if preferred_kind:
            return preferred_kind[0]
        return matches[0]
    if not projects:
        raise RuntimeError('no projects discovered')
    return projects[0]


def validate_endpoints(base: str, project_id: str, note_path: str | None) -> dict[str, bool]:
    status: dict[str, bool] = {}
    status['/'] = wait_http_ok(f'{base}/')
    status['/api/projects'] = wait_http_ok(f'{base}/api/projects')
    status['/api/projects/<project_id>'] = wait_http_ok(f'{base}/api/projects/{project_id}')
    status['/api/projects/<project_id>/graph'] = wait_http_ok(f'{base}/api/projects/{project_id}/graph')
    if note_path:
        status['/api/projects/<project_id>/note'] = wait_http_ok(f'{base}/api/projects/{project_id}/note?path={note_path}')
    else:
        status['/api/projects/<project_id>/note'] = False
    return status


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f'root not found: {root}')

    listener_pid = read_listener_pid(args.port)
    existing_cmd = cmdline_for_pid(listener_pid) if listener_pid else ''
    if listener_pid:
        if not is_textifai_viewer_process(existing_cmd):
            raise SystemExit(
                f'refusing to stop non-TextifAI process on {args.port}: pid={listener_pid} cmd={existing_cmd}'
            )
        if not args.kill_existing_textifai_viewer:
            raise SystemExit(
                f'TextifAI viewer already running on {args.port}: pid={listener_pid}. '
                'Pass --kill-existing-textifai-viewer to restart.'
            )
        stop_pid(listener_pid)

    pid_path = PID_PATH_DEFAULT if args.port == DEFAULT_PORT else Path(f'/tmp/textifai_viewer_{args.port}.pid')
    log_path = LOG_PATH_DEFAULT if args.port == DEFAULT_PORT else Path(f'/tmp/textifai_viewer_{args.port}.log')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = log_path.open('w', encoding='utf-8')
    cmd = [
        'uv', 'run', 'python', '-m', 'textifai.web_viewer.server',
        '--root', str(root),
        '--host', args.host,
        '--port', str(args.port),
    ]
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=log_fp, stderr=subprocess.STDOUT, start_new_session=True)

    base = f'http://127.0.0.1:{args.port}'
    if not wait_http_ok(f'{base}/api/projects', timeout_s=10.0):
        raise SystemExit(f'viewer did not become ready on {base}; check log {log_path}')
    listener_pid = read_listener_pid(args.port) or proc.pid
    pid_path.write_text(str(listener_pid), encoding='utf-8')

    projects_payload = load_json(f'{base}/api/projects')
    projects = projects_payload.get('projects') if isinstance(projects_payload, dict) else []
    if not isinstance(projects, list):
        raise SystemExit('invalid /api/projects payload')

    project = choose_project(projects, args.project_id_contains)
    project_id = str(project.get('project_id') or '')
    project_payload = load_json(f'{base}/api/projects/{project_id}')
    notes = project_payload.get('notes') if isinstance(project_payload, dict) else []
    note_path = notes[0]['path'] if isinstance(notes, list) and notes and isinstance(notes[0], dict) else None

    endpoint_status = validate_endpoints(base, project_id, note_path)
    summary = {
        'assessment': 'stable_viewer_server_ready' if all(endpoint_status.values()) else 'stable_viewer_server_partial',
        'root': str(root),
        'host': args.host,
        'port': args.port,
        'project_id': project_id,
        'pid': listener_pid,
        'pid_path': str(pid_path),
        'log_path': str(log_path),
        'stop_command': f'kill {listener_pid}',
        'endpoint_status': endpoint_status,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
