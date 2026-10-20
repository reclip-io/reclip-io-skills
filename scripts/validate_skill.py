#!/usr/bin/env python3
"""Offline structural and pinned-contract consistency checks; no dependencies."""
import ast
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'reclip'


def main():
    text = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\n'), 'Missing YAML frontmatter'
    header = text.split('---', 2)[1]
    assert re.search(r'^name: reclip$', header, re.M), 'Invalid name'
    assert re.search(r'^description: .+', header, re.M), 'Missing description'
    for md in [ROOT / 'README.md', *SKILL.rglob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', md.read_text(encoding='utf-8')):
            if '://' in link or link.startswith('#'):
                continue
            target = (md.parent / link.split('#')[0]).resolve()
            assert target.is_relative_to(ROOT), 'Reference escapes repository'
            assert target.exists(), 'Missing link: ' + link
    for path in ROOT.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 9))
    spec = importlib.util.spec_from_file_location('client', SKILL / 'scripts/reclip_api.py')
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    ops = json.loads((SKILL / 'references/operations.json').read_text())
    catalog = json.loads((SKILL / 'references/tool-catalog.json').read_text())
    assert ops['source'] == catalog['source'], 'Mixed backend snapshots'
    assert len(client.TOOLS) == len(set(client.TOOLS)) == len(catalog['source']['tool_codes']), 'Incomplete tool coverage'
    assert set(client.OPERATIONS.values()) == {(o['method'], o['path']) for o in ops['operations']}, 'Client differs from backend snapshot'
    assert set(client.TOOLS) == set(catalog['source']['tool_codes']), 'Tool catalog differs from product registry'
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    assert manifest['skills'][0]['path'] == 'skills/reclip'
    assert manifest['version'] == client.VERSION
    print('Validated: self-contained skill, Python 3.9 syntax, %d tools, %d operations.' % (len(client.TOOLS), len(client.OPERATIONS)))


if __name__ == '__main__':
    main()
