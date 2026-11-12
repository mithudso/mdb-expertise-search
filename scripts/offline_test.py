#!/usr/bin/env python3
"""macOS offline checks with process-tree egress denial and scratch-only test state."""
import argparse
import subprocess
import tempfile
from pathlib import Path

from test_isolation import prepare_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-fixture-port', type=int, action='append', default=[])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ['--']:
        args.command.pop(0)
    if not args.command:
        parser.error('a test command is required')
    if any(not 1 <= port <= 65535 for port in args.allow_fixture_port):
        parser.error('fixture ports must be in 1..65535')
    profile = '(version 1)\n(allow default)\n(deny network-outbound)\n'
    for port in sorted(set(args.allow_fixture_port)):
        # Only a listener created and owned by this test may be supplied here.
        profile += f'(allow network-outbound (remote tcp "localhost:{port}"))\n'
    with tempfile.TemporaryDirectory(prefix='mdbx-offline-') as scratch:
        prepare_environment(Path(scratch))
        return subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, *args.command],
                              check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
