from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from textifai.obsidian.setup import ObsidianProjectSetupConfig, prepare_obsidian_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a TextifAI project vault for Obsidian + VaERL.")
    parser.add_argument("--vault-root", required=True, help="Target vault root")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["existing_material", "new_project"],
        help="Bootstrap from existing material or initialize a new project",
    )
    parser.add_argument("--project-title", default=None)
    parser.add_argument("--source-root", default=None, help="Source documents for existing_material mode")
    parser.add_argument("--primary-language", default=None)
    parser.add_argument("--working-language", action="append", default=[])
    parser.add_argument("--build-bridge-plugin", action="store_true")
    parser.add_argument("--skip-plugin-install", action="store_true")
    parser.add_argument("--plugin-repo-root", default=None)
    parser.add_argument(
        "--importer-preference",
        choices=["textifai_bootstrap_staging", "obsidian_importer_manual_if_markdown"],
        default="textifai_bootstrap_staging",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = prepare_obsidian_project(
        ObsidianProjectSetupConfig(
            vault_root=args.vault_root,
            mode=args.mode,
            project_title=args.project_title,
            source_root=args.source_root,
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
