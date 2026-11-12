#!/usr/bin/env python3
"""Offline checks with process-tree egress denial and scratch-only test state."""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from test_isolation import prepare_environment

_PROC = Path('/proc')
_LINUX_TOOLS = {name: '/usr/bin/' + name for name in ('sudo', 'unshare', 'setpriv', 'env')}


def _interface_flags(name):
    # ioctl observes the current network namespace; an inherited sysfs mount may not.
    import fcntl
    import socket
    import struct

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as handle:
        request = struct.pack('256s', name.encode('ascii'))
        response = fcntl.ioctl(handle.fileno(), 0x8913, request)  # SIOCGIFFLAGS
    return struct.unpack_from('H', response, 16)[0]


def linux_isolated():
    """Prove an inherited empty namespace and irreversible unprivileged state."""
    try:
        uid, gid = os.getuid(), os.getgid()
        if uid == 0 or gid == 0 or os.geteuid() != uid or os.getegid() != gid or os.getgroups():
            return False
        status = dict(line.split(':', 1) for line in
                      (_PROC / 'self/status').read_text(encoding='ascii').splitlines() if ':' in line)
        if any([int(value) for value in status[key].split()] != [identity] * 4
               for key, identity in [('Uid', uid), ('Gid', gid)]):
            return False
        if status['Groups'].strip() or status['NoNewPrivs'].strip() != '1':
            return False
        if any(int(status[key].strip(), 16) != 0
               for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')):
            return False
        devices = (_PROC / 'net/dev').read_text(encoding='ascii').splitlines()
        if len(devices) < 3 or {line.split(':', 1)[0].strip()
                               for line in devices[2:] if line.strip()} != {'lo'}:
            return False
        flags = _interface_flags('lo')
        if flags & 1 or not flags & 8:  # IFF_UP must be clear; IFF_LOOPBACK must be set.
            return False
        routes = (_PROC / 'net/route').read_text(encoding='ascii').splitlines()
        header = ['Iface', 'Destination', 'Gateway', 'Flags', 'RefCnt', 'Use', 'Metric', 'Mask', 'MTU', 'Window', 'IRTT']
        if not routes or routes[0].split() != header or any(line.strip() for line in routes[1:]):
            return False
        # Linux can expose inert kernel null routes even with loopback down.
        # Only RTF_REJECT entries on that down interface are acceptable.
        for line in (_PROC / 'net/ipv6_route').read_text(encoding='ascii').splitlines():
            parts = line.split()
            if not parts:
                continue
            widths = (32, 2, 32, 2, 32, 8, 8, 8, 8)
            if len(parts) != 10 or parts[-1] != 'lo':
                return False
            if any(len(value) != width or any(ch not in '0123456789abcdefABCDEF' for ch in value)
                   for value, width in zip(parts[:-1], widths)):
                return False
            if not int(parts[8], 16) & 0x200:  # RTF_REJECT cannot deliver a packet.
                return False
        return True
    except (OSError, ValueError, KeyError, IndexError):
        return False


def linux_command(argv):
    """Create isolation, or reuse only a kernel-proven inherited guard."""
    inherited = linux_isolated()
    needed = ('env',) if inherited else ('sudo', 'unshare', 'setpriv', 'env')
    if any(not os.access(_LINUX_TOOLS[name], os.X_OK) for name in needed):
        raise ValueError('Linux offline checks require system sudo, unshare, setpriv and env')
    environment = [_LINUX_TOOLS['env'], '-i', '--',
                   *[key + '=' + value for key, value in os.environ.items()], *argv]
    if inherited:
        return environment
    if os.getuid() == 0 or os.geteuid() != os.getuid() or os.getgid() == 0:
        raise ValueError('Linux offline checks require a non-root runner')
    return [_LINUX_TOOLS['sudo'], '-n', '--', _LINUX_TOOLS['unshare'], '--net', '--',
            _LINUX_TOOLS['setpriv'], '--reuid', str(os.getuid()), '--regid', str(os.getgid()),
            '--clear-groups', '--inh-caps=-all', '--ambient-caps=-all', '--bounding-set=-all',
            '--no-new-privs', '--', *environment]

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
        if sys.platform == 'darwin':
            command = ['/usr/bin/sandbox-exec', '-p', profile, *args.command]
        elif sys.platform.startswith('linux'):
            if args.allow_fixture_port:
                parser.error('fixture-port exceptions require the macOS sandbox')
            try:
                command = linux_command(args.command)
            except ValueError as error:
                parser.error(str(error))
        else:
            parser.error('no supported process-tree network isolation on this platform')
        result = subprocess.run(command, check=False).returncode
        return result if result >= 0 else 128 - result


if __name__ == '__main__':
    raise SystemExit(main())
