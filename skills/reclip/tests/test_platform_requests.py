import copy
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

from test_reclip_api import FakeAPI, a


SKILL = Path(__file__).resolve().parents[1]
REQUESTS = SKILL / 'references' / 'platform-requests'
PAIRS = {
    'youtube-video-downloader': ('video_downloader', 'youtube'),
    'tiktok-video-downloader': ('video_downloader', 'tiktok'),
    'instagram-video-downloader': ('video_downloader', 'instagram'),
    'youtube-ai-clipper': ('ai_clipper', 'youtube'),
    'twitch-vod-clipper': ('ai_clipper', 'twitch'),
    'youtube-ai-broll': ('ai_broll', 'youtube'),
    'twitch-vod-ai-broll': ('ai_broll', 'twitch'),
    'youtube-ai-captions': ('ai_captions', 'youtube'),
    'youtube-transcript': ('youtube_transcript', 'youtube'),
    'tiktok-transcript': ('tiktok_transcript', 'tiktok'),
}


class PlatformRequestTests(unittest.TestCase):
    def test_templates_match_supported_sources_and_pinned_tool_fields(self):
        self.assertEqual({path.stem for path in REQUESTS.glob('*.json')}, set(PAIRS))
        catalog = json.loads((SKILL / 'references' / 'tool-catalog.json').read_text())
        tools = {tool['id']: tool for tool in catalog['tools']}
        mcp = json.loads((SKILL / 'references' / 'mcp-tools.json').read_text())
        mcp_tools = {tool['name']: tool for tool in mcp['tools']}
        for slug, (tool, platform) in PAIRS.items():
            with self.subTest(slug=slug):
                payload = a.read_json(REQUESTS / (slug + '.json'))
                self.assertEqual(a.job_payload(payload), payload)
                self.assertEqual(payload['tool'], tool)
                self.assertEqual(payload['maximum_credits'], 100)
                fields = tools[tool]['input_schema']
                self.assertLessEqual(set(payload['input']), set(fields['properties']))
                # Runtime schemas apply these declared defaults before dispatch.
                required = {
                    name for name in fields.get('required', [])
                    if 'default' not in fields['properties'][name]
                }
                self.assertLessEqual(required, set(payload['input']))
                self.assertNotIn('asset_id', payload['input'])
                source = urlsplit(payload['input']['source_url'])
                self.assertEqual(source.scheme, 'https')
                self.assertEqual(source.hostname, {
                    'youtube': 'www.youtube.com',
                    'tiktok': 'www.tiktok.com',
                    'instagram': 'www.instagram.com',
                    'twitch': 'www.twitch.tv',
                }[platform])
                if platform == 'twitch':
                    self.assertRegex(source.path, r'^/videos/[0-9]+$')
                if tool == 'video_downloader':
                    self.assertEqual(payload['input']['platform'], platform)
                    self.assertGreater(payload['input']['maximum_download_bytes'], 0)
                else:
                    self.assertNotIn('platform', payload['input'])
                if tool == 'ai_captions':
                    self.assertGreater(payload['input']['duration_seconds'], 0)
                    self.assertIn('caption_style', payload['input']['options'])
                entry = mcp_tools['reclip_' + tool]
                self.assertLessEqual(
                    {'input', 'maximum_credits', 'idempotency_key'},
                    set(entry['inputSchema']['required']),
                )

    def test_every_template_runs_with_a_lower_budget_and_resumes_the_original_job(self):
        with tempfile.TemporaryDirectory() as directory:
            for slug in PAIRS:
                with self.subTest(slug=slug):
                    payload = a.read_json(REQUESTS / (slug + '.json'))
                    original = copy.deepcopy(payload)
                    request = Path(directory) / (slug + '.json')
                    request.write_text(json.dumps(payload))
                    state = Path(directory) / (slug + '.state.json')
                    args = a.parser().parse_args([
                        'run', str(request), '--state', str(state),
                        '--maximum-credits', '25',
                    ])
                    client = FakeAPI()
                    result = a.execute(args, client)
                    self.assertEqual(result['status'], 'succeeded')
                    submissions = [call for call in client.calls if call[0] == 'submit']
                    self.assertEqual(len(submissions), 1)
                    self.assertEqual(submissions[0][2]['maximum_credits'], 25)
                    self.assertEqual(submissions[0][2]['input'], original['input'])
                    self.assertEqual(submissions[0][2]['tool'], original['tool'])
                    key = submissions[0][3]['idempotency']
                    self.assertTrue(key)
                    self.assertEqual(a.read_json(state, state=True)['idempotency_key'], key)
                    a.execute(args, client)
                    self.assertEqual(len([call for call in client.calls if call[0] == 'submit']), 1)
                    self.assertEqual(len([call for call in client.calls if call[0] == 'quote']), 1)
                    self.assertEqual(a.read_json(REQUESTS / (slug + '.json')), original)

    def test_platform_templates_do_not_authorize_spending_above_the_selected_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            for slug in PAIRS:
                with self.subTest(slug=slug):
                    args = a.parser().parse_args([
                        'submit', str(REQUESTS / (slug + '.json')),
                        '--state', str(Path(directory) / (slug + '.state.json')),
                        '--maximum-credits', '5',
                    ])
                    client = FakeAPI()
                    client.estimate = 6
                    with self.assertRaises(a.ClientError):
                        a.execute(args, client)
                    self.assertFalse(any(call[0] == 'submit' for call in client.calls))


if __name__ == '__main__':
    unittest.main()
