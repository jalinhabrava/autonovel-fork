import json
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from textifai.web_viewer.project_reader import ProjectCatalog
from textifai.web_viewer.server import _make_handler


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / 'tests' / 'fixtures' / 'textifai' / 'upload_staging' / 'sample_3ch.md'


def _multipart_body(fields: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f'----codex{uuid.uuid4().hex}'
    parts: list[bytes] = []
    for name, filename, data, content_type in fields:
        parts.append(f'--{boundary}\r\n'.encode('utf-8'))
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            ).encode('utf-8')
        )
        parts.append(data)
        parts.append(b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
    return b''.join(parts), boundary


class UploadStagingTests(unittest.TestCase):
    def _serve(self, repo_root: Path):
        catalog = ProjectCatalog([repo_root / 'runs'])
        registry = type('Registry', (), {'list_jobs': lambda self: [], 'get_job': lambda self, job_id: None, 'get_job_log': lambda self, job_id, max_chars=0: None})()
        handler = _make_handler(catalog, registry, repo_root=repo_root)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_upload_stages_valid_3_chapter_fixture_and_returns_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            runs_root = repo_root / 'runs'
            runs_root.mkdir(parents=True)
            (repo_root / 'tests').mkdir(parents=True)
            target = repo_root / 'tests' / 'fixtures' / 'textifai' / 'upload_staging'
            target.mkdir(parents=True)
            (target / 'sample_3ch.md').write_text(FIXTURE.read_text(encoding='utf-8'), encoding='utf-8')
            server, thread = self._serve(repo_root)
            try:
                body, boundary = _multipart_body([('files', 'sample_3ch.md', (target / 'sample_3ch.md').read_bytes(), 'text/markdown')])
                request = Request(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads', data=body, method='POST')
                request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
                request.add_header('Content-Length', str(len(body)))
                with urlopen(request) as response:
                    payload = json.loads(response.read().decode('utf-8'))
                session_id = payload['upload_session_id']
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads?upload_session_id={session_id}') as response:
                    staged = json.loads(response.read().decode('utf-8'))
                staged_root = repo_root / 'runs' / 'web_ingestion_uploads' / session_id
                staged_root_exists = staged_root.exists()
                staged_file_exists = (staged_root / 'sample_3ch.md').exists()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

        self.assertTrue(session_id.startswith('upl_'))
        self.assertEqual(len(payload['files']), 1)
        self.assertEqual(payload['files'][0]['status'], 'staged')
        self.assertEqual(payload['files'][0]['filename'], 'sample_3ch.md')
        self.assertEqual(staged['upload_session_id'], session_id)
        self.assertEqual(staged['files'][0]['filename'], 'sample_3ch.md')
        self.assertTrue(staged_root_exists)
        self.assertTrue(staged_file_exists)

    def test_upload_accepts_txt_and_rejects_narrow_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / 'runs').mkdir(parents=True)
            server, thread = self._serve(repo_root)
            try:
                accepted = [
                    ('note.txt', b'one\ntwo\nthree\n', 'text/plain'),
                    ('note.md', b'# one\n# two\n# three\n', 'text/markdown'),
                ]
                for filename, data, content_type in accepted:
                    body, boundary = _multipart_body([('files', filename, data, content_type)])
                    request = Request(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads', data=body, method='POST')
                    request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
                    request.add_header('Content-Length', str(len(body)))
                    with urlopen(request) as response:
                        payload = json.loads(response.read().decode('utf-8'))
                    self.assertEqual(payload['files'][0]['filename'], filename)

                rejected = [
                    ('note.pdf', b'%PDF-1.4', 'application/pdf', '.pdf'),
                    ('note.docx', b'PK\x03\x04', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
                    ('note.doc', b'\xd0\xcf\x11\xe0', 'application/msword', '.doc'),
                    ('note.weird', b'data', 'application/octet-stream', '.weird'),
                ]
                for filename, data, content_type, extension in rejected:
                    body, boundary = _multipart_body([('files', filename, data, content_type)])
                    request = Request(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads', data=body, method='POST')
                    request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
                    request.add_header('Content-Length', str(len(body)))
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request)
                    self.assertEqual(caught.exception.code, 400)
                    payload = json.loads(caught.exception.read().decode('utf-8'))
                    self.assertEqual(payload['error'], 'upload_validation_failed')
                    self.assertEqual(payload['extension'], extension)
                    self.assertIn(extension, payload['message'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

    def test_upload_rejects_path_traversal_empty_and_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / 'runs').mkdir(parents=True)
            server, thread = self._serve(repo_root)
            try:
                cases = [
                    ([('files', '../escape.md', b'x', 'text/markdown')], 'path traversal rejected'),
                    ([('files', 'empty.md', b'', 'text/markdown')], 'empty files rejected'),
                    ([('files', 'bad.pdf', b'%PDF', 'application/pdf')], 'unsupported extension'),
                ]
                for fields, expected_message in cases:
                    body, boundary = _multipart_body(fields)
                    request = Request(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads', data=body, method='POST')
                    request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
                    request.add_header('Content-Length', str(len(body)))
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request)
                    self.assertEqual(caught.exception.code, 400)
                    payload = json.loads(caught.exception.read().decode('utf-8'))
                    self.assertEqual(payload['error'], 'upload_validation_failed')
                    self.assertIn(expected_message, payload['message'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

    def test_upload_session_does_not_expose_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / 'runs').mkdir(parents=True)
            server, thread = self._serve(repo_root)
            try:
                body, boundary = _multipart_body([('files', 'sample.md', b'# one\n# two\n# three\n', 'text/markdown')])
                request = Request(f'http://127.0.0.1:{server.server_port}/api/ingestion/uploads', data=body, method='POST')
                request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
                request.add_header('Content-Length', str(len(body)))
                with urlopen(request) as response:
                    payload = json.loads(response.read().decode('utf-8'))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=1.0)

        self.assertNotIn('one', json.dumps(payload))
        self.assertNotIn('two', json.dumps(payload))
        self.assertNotIn('three', json.dumps(payload))
