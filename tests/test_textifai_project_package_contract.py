import json
import subprocess
import unittest
from pathlib import Path

from textifai.web_viewer.project_reader import ProjectCatalog, read_project

REPO = Path(__file__).resolve().parents[1]
EXPECTED = REPO / 'tests/fixtures/textifai/project_package_contract/expected'
PROJECT_ROOT = Path('/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai')
MANIFEST = PROJECT_ROOT / 'textifai.project.json'
REGISTRY = REPO / '.textifai_runs/registry.local.json'
HANDOFF = REPO / 'docs/handoffs/safepoint-106_project-package-persistent-20ch.md'
PRIVATE_HANDOFF = REPO / 'docs/handoffs/private/safepoint-106_project-package-persistent-20ch/decision_handoff_private.md'

REPORTS = [
    'current_runtime_output_audit_after_sp105d.json',
    'persistent_20ch_project_recovery_after_sp105d.json',
    'textifai_project_manifest_schema_v1_after_sp105d.json',
    'project_folder_structure_contract_after_sp105d.json',
    'ingestion_output_contract_after_sp105d.json',
    'editor_chapter_source_contract_after_sp105d.json',
    'chapter_mini_ingestion_contract_after_sp105d.json',
    'open_project_workspace_loader_after_sp105d.json',
    'future_txtfai_package_options_after_sp105d.json',
    'provider_run_summary_after_sp105d.json',
    'project_package_contract_decision_after_sp105d.json',
]


def read_report(name: str) -> dict:
    return json.loads((EXPECTED / name).read_text(encoding='utf-8'))


class TextifAIProjectPackageContractTests(unittest.TestCase):
    def test_reports_parse_and_are_commit_safe(self):
        for name in REPORTS:
            payload = read_report(name)
            text = json.dumps(payload, ensure_ascii=False)
            self.assertIn('assessment', payload, name)
            self.assertNotIn('/home/david/OnT/ESP 王者の杖 .md', text, name)
            self.assertNotIn('Me llamaron muchas cosas', text, name)

    def test_manifest_schema_v1_required_fields(self):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'], 'textifai.project')
        self.assertEqual(manifest['schema_version'], 1)
        for field in ['project_id', 'title', 'language', 'created_at', 'updated_at', 'textifai_version', 'source', 'paths', 'status', 'capabilities', 'privacy', 'dev', 'workspace_entry']:
            self.assertIn(field, manifest)
        self.assertEqual(manifest['status']['chapters_total'], 20)
        self.assertFalse(manifest['privacy']['safe_to_commit'])
        self.assertTrue(manifest['privacy']['contains_source_prose'])

    def test_manifest_product_paths_are_relative_and_not_tmp(self):
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn('/tmp/', serialized)
        self.assertNotIn('/home/david/OnT/', serialized)
        for key, value in manifest['paths'].items():
            if isinstance(value, str):
                self.assertFalse(Path(value).is_absolute(), key)

    def test_package_structure_and_chapters_exist(self):
        self.assertTrue((PROJECT_ROOT / 'markdown/Chapters').is_dir())
        chapters = sorted((PROJECT_ROOT / 'markdown/Chapters').glob('Ch_*.md'))
        self.assertEqual(len(chapters), 20)
        for folder in ['vaerl', 'graph', 'drafts/chapters', 'drafts/notes', 'patches/pending', 'patches/applied', 'patches/rejected', 'reports', 'dev/diagnostics', 'dev/raw_artifacts', 'dev/provider_outputs']:
            self.assertTrue((PROJECT_ROOT / folder).exists(), folder)

    def test_project_reader_detects_manifest_backed_project(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        projects = catalog.list_projects()
        self.assertTrue(projects)
        project = projects[0]
        self.assertEqual(project['kind'], 'textifai_project')
        self.assertEqual(project['chapter_count'], 20)
        self.assertGreater(project['markdown_note_count'], 11)
        self.assertGreater(project['graph_summary']['node_count'], 11)

    def test_workspace_loader_loads_manifest_project(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        project_ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        payload = read_project(project_ref)
        self.assertEqual(payload['project']['kind'], 'textifai_project')
        self.assertEqual(payload['overview']['chapters_processed'], 20)
        self.assertGreater(len(payload['notes']), 20)
        self.assertGreater(len(payload['graph']['nodes']), 11)

    def test_editor_chapter_source_uses_chapters_only(self):
        catalog = ProjectCatalog([PROJECT_ROOT])
        project_ref = catalog.get_project(catalog.list_projects()[0]['project_id'])
        payload = read_project(project_ref)
        chapter_notes = [note for note in payload['notes'] if note.get('kind') == 'chapter']
        self.assertEqual(len(chapter_notes), 20)
        self.assertTrue(all(note['path'].startswith('markdown/Chapters/') for note in chapter_notes))
        self.assertFalse(any('/Characters/' in note['path'] for note in chapter_notes))

    def test_registry_is_gitignored_and_points_to_manifest(self):
        self.assertTrue(REGISTRY.exists())
        registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
        manifests = [Path(item['manifest_path']) for item in registry.get('projects', [])]
        self.assertIn(MANIFEST, manifests)
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(REGISTRY)], cwd=REPO, text=True, capture_output=True)
        self.assertEqual(ignore.returncode, 0, ignore.stdout + ignore.stderr)

    def test_legacy_runtime_dev_fallback_and_real_project_preferred(self):
        mini = Path('/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z/viewer_project')
        catalog = ProjectCatalog([mini, PROJECT_ROOT])
        projects = catalog.list_projects()
        by_kind = {project['kind']: project for project in projects}
        self.assertIn('textifai_project', by_kind)
        self.assertIn('vault_or_run', by_kind)
        self.assertTrue(by_kind['textifai_project']['recommended'])
        self.assertGreater(by_kind['textifai_project']['chapter_count'], by_kind['vault_or_run']['chapter_count'])

    def test_future_txtfai_plan_and_handoffs_exist(self):
        future = read_report('future_txtfai_package_options_after_sp105d.json')
        self.assertEqual(future['recommended_now'], 'folder_bundle_with_textifai_project_json')
        self.assertIn('zip_package', future['future_options'])
        self.assertTrue(HANDOFF.exists())
        ignore = subprocess.run(['git', 'check-ignore', '-v', str(PRIVATE_HANDOFF)], cwd=REPO, text=True, capture_output=True)
        self.assertEqual(ignore.returncode, 0, ignore.stdout + ignore.stderr)


if __name__ == '__main__':
    unittest.main()
