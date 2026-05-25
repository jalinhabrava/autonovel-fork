from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_OUTPUT_ROOT = Path('/tmp/textifai_deepseek_model_discovery')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Discover visible DeepSeek models for current BYOK key.')
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument('--api-base-url', default=os.environ.get('AUTONOVEL_DEEPSEEK_API_BASE_URL', DEFAULT_API_BASE))
    return parser


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def run(args: argparse.Namespace) -> dict:
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not key:
        raise SystemExit('DEEPSEEK_API_KEY missing')
    url = args.api_base_url.rstrip('/') + '/models'
    req = Request(url, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8')
            status = getattr(resp, 'status', 200)
    except HTTPError as exc:
        return {
            'status': 'model_discovery_failed',
            'http_status': exc.code,
            'error_type': 'HTTPError',
            'error': str(exc),
            'timestamp_utc': _utc_stamp(),
            'api_base_url': args.api_base_url,
        }
    except URLError as exc:
        return {
            'status': 'model_discovery_failed',
            'http_status': None,
            'error_type': 'URLError',
            'error': str(exc),
            'timestamp_utc': _utc_stamp(),
            'api_base_url': args.api_base_url,
        }

    payload = json.loads(raw)
    models = payload.get('data', []) if isinstance(payload, dict) else []
    ids = [item.get('id') for item in models if isinstance(item, dict) and item.get('id')]
    deepseek_ids = sorted(ids)
    aliases = {
        'flash': [mid for mid in deepseek_ids if 'flash' in mid],
        'pro': [mid for mid in deepseek_ids if 'pro' in mid],
        'reasoner': [mid for mid in deepseek_ids if 'reasoner' in mid or 'thinking' in mid],
        'chat': [mid for mid in deepseek_ids if 'chat' in mid],
    }
    return {
        'status': 'completed',
        'http_status': status,
        'timestamp_utc': _utc_stamp(),
        'api_base_url': args.api_base_url,
        'visible_model_count': len(deepseek_ids),
        'visible_model_ids': deepseek_ids,
        'aliases': aliases,
    }


def main() -> int:
    args = build_parser().parse_args()
    summary = run(args)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    out = output_root / f'{_utc_stamp()}_model_discovery_summary.json'
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': summary['status'], 'summary_path': str(out), 'visible_model_count': summary.get('visible_model_count')}))
    return 0 if summary['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
