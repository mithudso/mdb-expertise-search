#!/usr/bin/env python3
"""Offline checks with process-tree egress denial and scratch-only test state."""
import argparse
import json
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
        route_text = (_PROC / 'net/route').read_text(encoding='ascii')
        routes = route_text.splitlines()
        header = ['Iface', 'Destination', 'Gateway', 'Flags', 'RefCnt', 'Use', 'Metric', 'Mask', 'MTU', 'Window', 'IRTT']
        if route_text and (not routes or routes[0].split() != header or
                           any(line.strip() for line in routes[1:])):
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



def _no_new_privileges():
    try:
        rows = dict(line.split(':', 1) for line in
                    (_PROC / 'self/status').read_text(encoding='ascii').splitlines() if ':' in line)
        return rows.get('NoNewPrivs', '').strip() == '1'
    except (OSError, ValueError):
        return False


def linux_isolation_diagnostic():
    """Return only numeric kernel identity/network metadata, never raw proc text."""
    state = {'uid': os.getuid(), 'euid': os.geteuid(), 'gid': os.getgid(),
             'egid': os.getegid(), 'groups': os.getgroups()}
    try:
        status = dict(line.split(':', 1) for line in
                      (_PROC / 'self/status').read_text(encoding='ascii').splitlines() if ':' in line)
        state['status_uids'] = [int(value) for value in status['Uid'].split()]
        state['status_gids'] = [int(value) for value in status['Gid'].split()]
        state['status_groups'] = [int(value) for value in status['Groups'].split()]
        state['no_new_privs'] = int(status['NoNewPrivs'].strip())
        state['caps'] = {key: int(status[key].strip(), 16)
                         for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')}
    except (OSError, ValueError, KeyError) as error:
        state['status_error'] = {'type': type(error).__name__, 'errno': getattr(error, 'errno', None)}
    try:
        devices = (_PROC / 'net/dev').read_text(encoding='ascii').splitlines()
        names = [line.split(':', 1)[0].strip() for line in devices[2:] if line.strip()]
        state['interfaces'] = {'count': len(names), 'loopback_seen': 'lo' in names,
                               'other_count': sum(name != 'lo' for name in names)}
        if 'lo' in names:
            state['interfaces']['loopback_flags'] = _interface_flags('lo')
    except (OSError, ValueError) as error:
        state['interface_error'] = {'type': type(error).__name__, 'errno': getattr(error, 'errno', None)}
    for version, name in [('ipv4', 'route'), ('ipv6', 'ipv6_route')]:
        try:
            route_text = (_PROC / 'net' / name).read_text(encoding='ascii')
            rows = route_text.splitlines()
            if version == 'ipv4':
                header = ['Iface', 'Destination', 'Gateway', 'Flags', 'RefCnt', 'Use',
                          'Metric', 'Mask', 'MTU', 'Window', 'IRTT']
                fields = rows[0].split() if rows else []
                state['ipv4_file_empty'] = route_text == ''
                state['ipv4_header_matches'] = fields == header
                state['ipv4_header_field_count'] = len(fields)
                rows = rows[1:]
            fields = [row.split() for row in rows if row.strip()]
            flag_at = 3 if version == 'ipv4' else 8
            state[version] = {'rows': len(fields),
                              'column_widths': [[len(value) for value in row] for row in fields],
                              'flags': [int(row[flag_at], 16) for row in fields],
                              'on_loopback': [(row[0] if version == 'ipv4' else row[-1]) == 'lo'
                                              for row in fields]}
            if version == 'ipv6':
                widths = (32, 2, 32, 2, 32, 8, 8, 8, 8)
                state[version]['format_ok'] = all(
                    len(row) == 10 and all(
                        len(value) == width and all(ch in '0123456789abcdefABCDEF' for ch in value)
                        for value, width in zip(row[:-1], widths)) for row in fields)
                state[version]['prefix_lengths'] = [[int(row[1], 16), int(row[3], 16)]
                                                     for row in fields]
                state[version]['metrics_refcounts_uses'] = [
                    [int(row[index], 16) for index in (5, 6, 7)] for row in fields]
        except (OSError, ValueError, IndexError) as error:
            state[version + '_error'] = {'type': type(error).__name__, 'errno': getattr(error, 'errno', None)}
    interfaces = state.get('interfaces', {})
    flags = interfaces.get('loopback_flags', 0)
    caps = state.get('caps', {})
    ipv4, ipv6 = state.get('ipv4', {}), state.get('ipv6', {})
    predicates = {
        'uid_ok': state['uid'] != 0 and state['uid'] == state['euid'],
        'gid_ok': state['gid'] != 0 and state['gid'] == state['egid'],
        'groups_empty': state['groups'] == [] and state.get('status_groups') == [],
        'status_ids_ok': state.get('status_uids') == [state['uid']] * 4 and
                         state.get('status_gids') == [state['gid']] * 4,
        'caps_zero': len(caps) == 5 and all(value == 0 for value in caps.values()),
        'no_new_privs': state.get('no_new_privs') == 1,
        'interfaces_only_lo': interfaces.get('count') == 1 and
                              interfaces.get('loopback_seen') is True and
                              interfaces.get('other_count') == 0,
        'lo_down_loopback': bool(flags & 8) and not flags & 1,
        'routeheader_ok': state.get('ipv4_file_empty') is True or
                          state.get('ipv4_header_matches') is True,
        'ipv4_empty': ipv4.get('rows') == 0 and 'ipv4_error' not in state,
        'ipv6_reject_only': ipv6.get('format_ok') is True and
                            all(ipv6.get('on_loopback', [])) and
                            all(value & 0x200 for value in ipv6.get('flags', [])) and
                            'ipv6_error' not in state,
    }
    state['predicates'] = predicates
    state['failed_predicates'] = [name for name, passed in predicates.items() if not passed]
    return json.dumps(state, sort_keys=True)

def linux_command(argv):
    """Create isolation, or reuse only a kernel-proven inherited guard."""
    inherited = linux_isolated()
    if not inherited and _no_new_privileges():
        raise ValueError('Linux inherited isolation attestation failed: ' +
                         linux_isolation_diagnostic())
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
