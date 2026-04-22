from __future__ import annotations

import argparse
import json
from pathlib import Path

from textifai.obsidian.json_import import import_json_to_vault


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a normalized fiction JSON payload into an Obsidian-style vault.")
    parser.add_argument("--source-json", required=True)
    parser.add_argument("--vault-root", required=True)
    args = parser.parse_args()

    audit = import_json_to_vault(
        source_json=Path(args.source_json),
        vault_root=Path(args.vault_root),
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
