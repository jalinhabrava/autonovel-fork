from __future__ import annotations

import json
import unittest
from pathlib import Path


PLUGIN_ROOT = Path("/home/david/projects/autonovel-fork/integrations/obsidian-textifai-bridge")


class TextifAIObsidianBridgePluginTests(unittest.TestCase):
    def test_plugin_scaffold_contains_required_obsidian_files(self):
        self.assertTrue((PLUGIN_ROOT / "manifest.json").exists())
        self.assertTrue((PLUGIN_ROOT / "package.json").exists())
        self.assertTrue((PLUGIN_ROOT / "src" / "main.ts").exists())
        self.assertTrue((PLUGIN_ROOT / "INSTALL.md").exists())
        self.assertTrue((PLUGIN_ROOT / "README.md").exists())

    def test_manifest_and_source_reflect_bridge_snapshot_purpose(self):
        manifest = json.loads((PLUGIN_ROOT / "manifest.json").read_text(encoding="utf-8"))
        source = (PLUGIN_ROOT / "src" / "main.ts").read_text(encoding="utf-8")
        install = (PLUGIN_ROOT / "INSTALL.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["id"], "textifai-bridge")
        self.assertIn("metadataCache.on(\"resolved\",", source)
        self.assertIn("metadataCache.on(\"changed\",", source)
        self.assertIn("getMarkdownFiles()", source)
        self.assertIn("cachedRead(file)", source)
        self.assertIn("resolvedLinks", source)
        self.assertIn("unresolvedLinks", source)
        self.assertIn("frontmatter_links", source)
        self.assertIn("embeds", source)
        self.assertIn("writeSnapshotAtomically", source)
        self.assertIn("export_complete", source)
        self.assertIn("installationId", source)
        self.assertIn("schema_version: SNAPSHOT_SCHEMA_VERSION", source)
        self.assertIn(".obsidian/plugins/textifai-bridge/", install)
