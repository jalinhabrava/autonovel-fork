from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.obsidian import evaluate_obsidian_operational_readiness
from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Short TextifAI + Obsidian operational commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a new project vault or import existing material.")
    init_parser.add_argument("--vault-root", required=True)
    init_parser.add_argument("--project-title", default=None)
    init_parser.add_argument("--source-root", default=None, help="If present, init imports existing material.")
    init_parser.add_argument(
        "--use-vault-root-as-source",
        action="store_true",
        help="Treat the target folder itself as existing author material to ingest while converting it into a vault.",
    )
    init_parser.add_argument("--primary-language", default=None)
    init_parser.add_argument("--working-language", action="append", default=[])
    init_parser.add_argument("--build-bridge-plugin", action="store_true")
    init_parser.add_argument("--skip-plugin-install", action="store_true")
    init_parser.add_argument("--plugin-repo-root", default=None)
    init_parser.add_argument(
        "--importer-preference",
        choices=["textifai_bootstrap_staging", "obsidian_importer_manual_if_markdown"],
        default="textifai_bootstrap_staging",
    )

    status_parser = subparsers.add_parser("status", help="Inspect operational readiness for a vault.")
    status_parser.add_argument("--vault-root", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        readiness = evaluate_obsidian_operational_readiness(Path(args.vault_root))
        print(json.dumps(asdict(readiness), indent=2, ensure_ascii=False))
        return 0

    mode = "existing_material" if (args.source_root or args.use_vault_root_as_source) else "new_project"
    result = prepare_obsidian_project(
        ObsidianProjectSetupConfig(
            vault_root=args.vault_root,
            mode=mode,
            project_title=args.project_title,
            source_root=(args.source_root or args.vault_root) if args.use_vault_root_as_source else args.source_root,
            primary_language=args.primary_language,
            working_languages=list(args.working_language),
            install_bridge_plugin=not args.skip_plugin_install,
            build_bridge_plugin=args.build_bridge_plugin,
            plugin_repo_root=args.plugin_repo_root,
            importer_preference=args.importer_preference,
        ),
        repo_root=REPO_ROOT,
    )
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
