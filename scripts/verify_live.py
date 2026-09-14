#!/usr/bin/env python3
"""Optional authenticated GET-only deployment check. Never creates assets or jobs."""
import importlib.util
import json
from pathlib import Path
import sys

script = Path(__file__).resolve().parents[1] / 'skills/reclip/scripts/reclip_api.py'
spec = importlib.util.spec_from_file_location('client', script)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def main():
    try:
        client = a.Client()
        client.call('identity')
        catalog = client.call('tools')
        names = {tool['id'] for tool in catalog['data']}
        if not set(a.TOOLS).issubset(names):
            raise a.ClientError('Live catalog is missing a bundled tool.')
        snapshots = {tool['id']: tool for tool in a.CATALOG['tools']}
        for tool in a.TOOLS:
            detail = client.call('tool', tool)
            if detail.get('id') != tool or detail.get('input_schema') != snapshots[tool]['input_schema']:
                raise a.ClientError('Live tool identity differs from the bundled contract.')
        client.call('usage')
        print(json.dumps({'read_only_checks': 'passed', 'tools_read': len(a.TOOLS), 'paid_execution_tested': False}))
        return 0
    except (a.ClientError, KeyError, TypeError, ValueError):
        print('Read-only deployment verification failed. Check API enablement, configured origin, key, paid eligibility and scopes. No paid job was submitted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
