"""Linux command and inherited isolation contracts; all fixtures are synthetic."""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        spec = importlib.util.spec_from_file_location('linux_offline_guard', ROOT / 'scripts/offline_test.py')
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    finally:
        sys.path[:] = previous


@pytest.fixture
def guard(monkeypatch):
    return module()


@pytest.fixture
def isolated(guard, tmp_path, monkeypatch):
    proc = tmp_path / 'proc'
    (proc / 'self').mkdir(parents=True)
    (proc / 'net').mkdir()
    (proc / 'self/status').write_text(
        'Uid:\t1001\t1001\t1001\t1001\nGid:\t1002\t1002\t1002\t1002\nGroups:\n'
        'CapInh:\t0000000000000000\nCapPrm:\t0000000000000000\nCapEff:\t0000000000000000\n'
        'CapBnd:\t0000000000000000\nCapAmb:\t0000000000000000\nNoNewPrivs:\t1\n'.replace('\\t', '\t').replace('\\n', '\n'))
    (proc / 'net/dev').write_text('Inter-| Receive | Transmit\n face |bytes packets|bytes packets\n lo: 0 0\n'.replace('\\n', '\n'))
    (proc / 'net/route').write_text('Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n'.replace('\\n', '\n'))
    (proc / 'net/ipv6_route').write_text('')
    sysfs = tmp_path / 'sys/class/net/lo'
    sysfs.mkdir(parents=True)
    (sysfs / 'flags').write_text('0x8')
    monkeypatch.setattr(guard, '_PROC', proc)
    monkeypatch.setattr(guard, '_interface_flags', lambda name: int((sysfs / 'flags').read_text(), 16))
    for name, value in [('getuid', 1001), ('geteuid', 1001), ('getgid', 1002), ('getegid', 1002)]:
        monkeypatch.setattr(guard.os, name, lambda value=value: value)
    monkeypatch.setattr(guard.os, 'getgroups', list)
    return proc, sysfs


def test_privileged_command_drops_every_privilege_after_namespace(guard, monkeypatch):
    monkeypatch.setattr(guard, 'linux_isolated', lambda: False, raising=False)
    monkeypatch.setattr(guard, '_no_new_privileges', lambda: False)
    monkeypatch.setattr(guard.os, 'getuid', lambda: 1001)
    monkeypatch.setattr(guard.os, 'geteuid', lambda: 1001)
    monkeypatch.setattr(guard.os, 'getgid', lambda: 1002)
    monkeypatch.setattr(guard.os, 'access', lambda *a: True)
    monkeypatch.setattr(guard, 'prepare_environment', lambda root: None)
    monkeypatch.setattr(guard.sys, 'platform', 'linux')
    monkeypatch.setattr(guard.sys, 'argv', ['offline_test', '--', 'python', 'synthetic.py'])
    calls = []
    monkeypatch.setattr(guard.subprocess, 'run', lambda command, **kw: (
        calls.append(command), SimpleNamespace(returncode=0))[1])
    assert guard.main() == 0
    command = calls[0]
    setpriv = command.index('/usr/bin/setpriv')
    assert command[:setpriv] == ['/usr/bin/sudo', '-n', '--', '/usr/bin/unshare', '--net', '--']
    expected = ['--reuid', '1001', '--regid', '1002', '--clear-groups',
                '--inh-caps=-all', '--ambient-caps=-all', '--bounding-set=-all',
                '--no-new-privs', '--', '/usr/bin/env', '-i', '--']
    assert command[setpriv + 1:setpriv + 1 + len(expected)] == expected
    assert command[-2:] == ['python', 'synthetic.py']


def test_proven_nested_guard_requires_no_new_sudo_and_fresh_scratch(guard, isolated, monkeypatch):
    assert guard.linux_isolated()
    monkeypatch.setattr(guard.os, 'access', lambda path, mode: path == '/usr/bin/env')
    command = guard.linux_command(['python', 'synthetic.py'])
    assert command[:3] == ['/usr/bin/env', '-i', '--']
    assert '/usr/bin/sudo' not in command
    roots, commands = [], []
    prepare = guard.prepare_environment
    def prepared(root):
        roots.append(root)
        prepare(root)
    monkeypatch.setattr(guard, 'prepare_environment', prepared)
    monkeypatch.setattr(guard.sys, 'platform', 'linux')
    monkeypatch.setattr(guard.sys, 'argv', ['offline_test', '--', 'python', 'synthetic.py'])
    monkeypatch.setattr(guard.os, 'environ', dict(os.environ, SYNTHETIC_AUTH_TOKEN='synthetic'))
    monkeypatch.setattr(guard.subprocess, 'run', lambda command, **kw: (
        commands.append(command), SimpleNamespace(returncode=0))[1])
    assert guard.main() == guard.main() == 0
    assert len(roots) == 2 and roots[0] != roots[1] and not any(path.exists() for path in roots)
    for command, root in zip(commands, roots):
        assert command[:3] == ['/usr/bin/env', '-i', '--']
        assert 'HOME=' + str(root / 'home') in command
        assert 'MDBX_TEST_ISOLATION_ROOT=' + str(root) in command
        assert not any(value.startswith('SYNTHETIC_AUTH_TOKEN=') for value in command)
        assert any(value.startswith('PYTHONPATH=') and str(root / 'bootstrap') in value for value in command)


@pytest.mark.parametrize('unsafe', [
    'uid-root', 'effective-uid', 'gid-root', 'effective-gid', 'saved-uid', 'saved-gid',
    'groups', 'status-groups', 'NoNewPrivs', 'CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb',
    'missing-status', 'malformed-status', 'extra-interface', 'missing-interface',
    'up-loopback', 'not-loopback', 'ipv4-route', 'ipv6-delivery-route', 'ipv6-other-interface',
    'malformed-ipv6', 'missing-routes', 'flags-error',
])
def test_unsafe_process_state_never_passes_env_attestation(guard, isolated, monkeypatch, unsafe):
    proc, sysfs = isolated
    monkeypatch.setenv('MDBX_NETWORK_ISOLATED', '1')
    monkeypatch.setenv('MDBX_OFFLINE_ISOLATED', '1')
    status = proc / 'self/status'
    if unsafe in {'uid-root', 'effective-uid', 'gid-root', 'effective-gid'}:
        name, value = {'uid-root': ('getuid', 0), 'effective-uid': ('geteuid', 0),
                       'gid-root': ('getgid', 0), 'effective-gid': ('getegid', 0)}[unsafe]
        monkeypatch.setattr(guard.os, name, lambda: value)
    elif unsafe == 'groups':
        monkeypatch.setattr(guard.os, 'getgroups', lambda: [1002])
    elif unsafe in {'saved-uid', 'saved-gid'}:
        original = '1001\t1001\t1001\t1001' if unsafe == 'saved-uid' else '1002\t1002\t1002\t1002'
        status.write_text(status.read_text().replace(original.replace('\\t', '\t'), '1001\t1001\t0\t1001'.replace('\\t', '\t')))
    elif unsafe == 'status-groups':
        status.write_text(status.read_text().replace('Groups:', 'Groups: 1002'))
    elif unsafe in {'NoNewPrivs', 'CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'}:
        text = status.read_text()
        old = unsafe + ':\t' + ('1' if unsafe == 'NoNewPrivs' else '0000000000000000')
        new = unsafe + ':\t' + ('0' if unsafe == 'NoNewPrivs' else '0000000000000001')
        status.write_text(text.replace(old.replace('\\t', '\t'), new.replace('\\t', '\t')))
    elif unsafe == 'missing-status':
        status.unlink()
    elif unsafe == 'malformed-status':
        status.write_text('Uid: invalid')
    elif unsafe in {'extra-interface', 'missing-interface'}:
        (proc / 'net/dev').write_text('Inter-| Receive | Transmit\n face |bytes packets|bytes packets\n'.replace('\\n', '\n')
                                     + ('lo: 0\neth0: 0\n'.replace('\\n', '\n') if unsafe == 'extra-interface' else ''))
    elif unsafe in {'up-loopback', 'not-loopback'}:
        (sysfs / 'flags').write_text('0x9' if unsafe == 'up-loopback' else '0x0')
    elif unsafe == 'ipv4-route':
        with (proc / 'net/route').open('a') as stream:
            stream.write('lo 00000000 00000000 0001 0 0 0 00000000 0 0 0\n'.replace('\\n', '\n'))
    elif unsafe.startswith('ipv6-'):
        reject = unsafe == 'ipv6-other-interface'
        (proc / 'net/ipv6_route').write_text(
            '0' * 32 + ' 00 ' + '0' * 32 + ' 00 ' + '0' * 32 +
            ' ffffffff 00000001 00000000 ' + ('00200200 eth0' if reject else '00000001 lo') + '\n'.replace('\\n', '\n'))
    elif unsafe == 'malformed-ipv6':
        (proc / 'net/ipv6_route').write_text('malformed')
    elif unsafe == 'missing-routes':
        (proc / 'net/route').unlink()
    elif unsafe == 'flags-error':
        def fail(name):
            raise OSError('synthetic ioctl refusal')
        monkeypatch.setattr(guard, '_interface_flags', fail)
    assert guard.linux_isolated() is False


def test_only_inert_reject_ipv6_rows_on_down_loopback_are_accepted(guard, isolated):
    proc, _ = isolated
    (proc / 'net/ipv6_route').write_text(
        '0' * 32 + ' 00 ' + '0' * 32 + ' 00 ' + '0' * 32 +
        ' ffffffff 00000001 00000000 00200200 lo\n'.replace('\\n', '\n'))
    assert guard.linux_isolated()


@pytest.mark.parametrize('inherited', [True, False])
def test_missing_required_system_tool_fails_closed(guard, monkeypatch, inherited):
    monkeypatch.setattr(guard, 'linux_isolated', lambda: inherited)
    monkeypatch.setattr(guard, '_no_new_privileges', lambda: False)
    monkeypatch.setattr(guard.os, 'access', lambda *a: False)
    with pytest.raises(ValueError, match='require system'):
        guard.linux_command(['synthetic'])


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_signal_status_143_is_preserved(guard, monkeypatch, platform):
    monkeypatch.setattr(guard, 'prepare_environment', lambda root: None)
    monkeypatch.setattr(guard.sys, 'platform', platform)
    monkeypatch.setattr(guard.sys, 'argv', ['offline_test', '--', 'synthetic'])
    monkeypatch.setattr(guard, 'linux_command', lambda argv: ['synthetic'])
    monkeypatch.setattr(guard.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=-15))
    assert guard.main() == 143


def _blocked(phase='python-parent', *, collect=False):
    import errno
    import json
    import socket
    import sys

    assert phase in {'python-parent', 'python-child'}
    labels = {errno.ENETUNREACH: 'ENETUNREACH', errno.EAFNOSUPPORT: 'EAFNOSUPPORT',
              errno.EADDRNOTAVAIL: 'EADDRNOTAVAIL', errno.ECONNREFUSED: 'ECONNREFUSED',
              errno.ETIMEDOUT: 'ETIMEDOUT'}
    observations = []
    def emit(case, operation, outcome, number=None):
        row = {'phase': phase, 'case': case, 'operation': operation, 'outcome': outcome,
               'family': 'ipv4' if case.endswith('v4') else 'ipv6',
               'errno': number if type(number) is int else None,
               'code': labels.get(number, 'UNKNOWN') if outcome != 'attempt' else None}
        print('MDBX_EGRESS ' + json.dumps(row, sort_keys=True), file=sys.stderr, flush=True)
        return row
    cases = [('doc-v4', '192.0.2.1', socket.AF_INET),
             ('loopback-v4', '127.0.0.1', socket.AF_INET),
             ('doc-v6', '2001:db8::1', socket.AF_INET6),
             ('loopback-v6', '::1', socket.AF_INET6)]
    for case, host, family in cases:
        operation = 'socket'
        emit(case, operation, 'attempt')
        try:
            with socket.socket(family, socket.SOCK_STREAM) as handle:
                handle.settimeout(1)
                operation = 'connect'
                emit(case, operation, 'attempt')
                handle.connect((host, 9))
        except OSError as error:
            outcome = 'timeout' if isinstance(error, TimeoutError) else 'error'
            row = emit(case, operation, outcome, error.errno)
            assert outcome == 'error', 'kernel denial not proven'
            assert collect or error.errno in {
                errno.ENETUNREACH, errno.EAFNOSUPPORT}, 'kernel denial not proven'
            observations.append(row)
        except Exception:  # noqa: BLE001 - diagnostics never include arbitrary error text
            emit(case, operation, 'error')
            raise AssertionError('unknown proof failure') from None
        else:
            emit(case, operation, 'connected')
            raise AssertionError('connection escaped')
    return observations


def _egress_probe():
    import inspect

    body = inspect.getsource(_blocked)
    child = body + "\ntry:\n records = _blocked('python-child', collect=True)\n if any(row['code'] not in {'ENETUNREACH','EAFNOSUPPORT'} for row in records): raise SystemExit(1)\nexcept AssertionError:\n raise SystemExit(1)\n"
    node = """
const net = require('node:net'), cp = require('node:child_process');
const phase = 'node-child';
let rejected = false;
const codes = new Set(['ENETUNREACH','EAFNOSUPPORT','EADDRNOTAVAIL','ECONNREFUSED','ETIMEDOUT','ENOENT']);
function emit(id, operation, outcome, error) {
  const row = {phase, case:id, operation, outcome, family:id === null ? null : id.endsWith('v4') ? 'ipv4' : 'ipv6',
    errno:Number.isInteger(error?.errno) ? error.errno : null,
    code:outcome === 'attempt' ? null : codes.has(error?.code) ? error.code : 'UNKNOWN'};
  console.error('MDBX_EGRESS ' + JSON.stringify(row));
}
async function blocked(id, host, family) {
  await new Promise((resolve, reject) => {
    emit(id, 'socket', 'attempt');
    let socket;
    try { socket = net.createConnection({host, port:9, family}); }
    catch (error) { emit(id, 'socket', 'error', error);
      if (!['ENETUNREACH', 'EAFNOSUPPORT'].includes(error.code)) rejected = true;
      resolve(); return; }
    emit(id, 'connect', 'attempt');
    socket.setTimeout(1000);
    socket.on('connect', () => { emit(id,'connect','connected'); socket.destroy(); reject(Error('escaped')); });
    socket.on('timeout', () => { emit(id,'connect','timeout'); socket.destroy(); reject(Error('timeout')); });
    socket.on('error', error => {
      emit(id, 'connect', 'error', error);
      if (!['ENETUNREACH', 'EAFNOSUPPORT'].includes(error.code)) rejected = true;
      resolve(); // Collect all denied cases; the strict verdict follows the complete chain.
    });
  });
}
(async () => {
  for (const [id,host,family] of [['doc-v4','192.0.2.1',4],['loopback-v4','127.0.0.1',4],
    ['doc-v6','2001:db8::1',6],['loopback-v6','::1',6]]) await blocked(id,host,family);
  emit(null, 'spawn', 'attempt');
  const child = cp.spawnSync(process.argv[1], ['-c', process.argv[2]], {stdio:'inherit'});
  if (child.status !== 0) { emit(null,'spawn','error',child.error); rejected = true; }
  if (rejected) process.exitCode=1;
})().catch(() => { process.exitCode=1; });
"""
    probe = ("import json,os,subprocess,sys\n" + body +
             "\ntry:\n parent_records = _blocked('python-parent', collect=True)\nexcept AssertionError:\n raise SystemExit(1)\n")
    probe += """def spawn_event(outcome, number=None):
 print('MDBX_EGRESS '+json.dumps({'phase':'python-parent','case':None,'operation':'spawn','outcome':outcome,'family':None,'errno':number,'code':'UNKNOWN' if outcome!='attempt' else None}),file=sys.stderr,flush=True)
spawn_event('attempt')
try:
 result=subprocess.run(["node","-e",NODE,sys.executable,CHILD],check=False,timeout=10)
except subprocess.TimeoutExpired:
 spawn_event('timeout');raise SystemExit(1)
except OSError as error:
 spawn_event('error',error.errno);raise SystemExit(1)
if result.returncode or any(row['code'] not in {'ENETUNREACH','EAFNOSUPPORT'} for row in parent_records):
 spawn_event('error');raise SystemExit(1)
print(json.dumps({"home":os.environ["HOME"],"root":os.environ["MDBX_TEST_ISOLATION_ROOT"]}))
""".replace('NODE', repr(node)).replace('CHILD', repr(child))
    return probe, node


def test_egress_probe_compiles_before_linux_execution():
    probe, _node = _egress_probe()
    compile(probe, '<Linux descendant proof>', 'exec')
    result = subprocess.run(['node', '--check'], input=_node, text=True,
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 0, result.stderr


def _kernel_metadata(proc=Path('/proc')):
    release = os.uname().release
    safe_release = release if len(release) <= 128 and all(
        ch.isascii() and (ch.isalnum() or ch in '._+-') for ch in release) else 'unrecognized'
    row = {'kernel_release': safe_release, 'ipv6_address_read': False}
    try:
        entries = (proc / 'net/if_inet6').read_bytes().splitlines()
        row.update(ipv6_address_read=True,
                   ipv6_address_entries=sum(bool(entry.strip()) for entry in entries))
    except OSError as error:
        row['ipv6_address_error'] = {'type': type(error).__name__, 'errno': error.errno}
    return row


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='actual Linux namespace proof')
def test_actual_linux_guard_is_inherited_by_python_and_node(tmp_path):
    import shutil

    guard = module()
    # Running this test outside the offline launcher fails before opening sockets.
    assert guard.linux_isolated(), guard.linux_isolation_diagnostic()
    assert shutil.which('node'), 'the maintained CI setup supplies Node'
    # pytest mocks connect; the fresh Python parent probe below performs the
    # actual four-address checks before its Node and Python descendants do so.
    probe, _node = _egress_probe()
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/offline_test.py'), '--',
                             sys.executable, '-c', probe],
                            capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, json.dumps(_kernel_metadata(), sort_keys=True) + '\n' + result.stderr[-8000:]
    row = json.loads(result.stdout)
    assert Path(row['home']) == Path(row['root']) / 'home'
    assert not Path(row['root']).exists()
    observations = [json.loads(line.removeprefix('MDBX_EGRESS '))
                    for line in result.stderr.splitlines() if line.startswith('MDBX_EGRESS ')]
    errors = [event for event in observations if event['outcome'] == 'error'
              and event['case'] is not None]
    expected = {(phase, case) for phase in ['python-parent', 'node-child', 'python-child']
                for case in ['doc-v4', 'loopback-v4', 'doc-v6', 'loopback-v6']}
    assert len(errors) == 12 and {(event['phase'], event['case']) for event in errors} == expected
    assert all(event['code'] in {'ENETUNREACH', 'EAFNOSUPPORT'} for event in errors)


def test_failed_attestation_metadata_is_numeric_and_excludes_private_text(guard, isolated, monkeypatch):
    proc, _sysfs = isolated
    monkeypatch.setenv('SYNTHETIC_AUTH_TOKEN', 'SYNTH_SECRET')
    with (proc / 'self/status').open('a') as stream:
        stream.write('Name: SYNTH_SECRET\nUnrelatedPath: /private/SYNTH_SECRET\n')
    row = json.loads(guard.linux_isolation_diagnostic())
    assert row['failed_predicates'] == [] and all(row['predicates'].values())
    assert 'SYNTH_SECRET' not in json.dumps(row)
    assert row['uid'] == row['euid'] == 1001
    assert row['gid'] == row['egid'] == 1002 and row['groups'] == []
    assert row['status_uids'] == [1001] * 4 and row['status_gids'] == [1002] * 4
    assert row['no_new_privs'] == 1 and set(row['caps'].values()) == {0}
    assert row['interfaces'] == {'count': 1, 'loopback_seen': True, 'other_count': 0,
                                 'loopback_flags': 8}
    assert row['ipv4_header_matches'] and row['ipv4']['rows'] == row['ipv6']['rows'] == 0
    (proc / 'self/status').write_text('Uid: SYNTH_SECRET/private/path')
    (proc / 'net/dev').write_text('header\nheader\nSYNTH_SECRET: 0\n')
    (proc / 'net/route').write_text('SYNTH_SECRET header\nSYNTH_SECRET private data invalid\n')
    diagnostic = guard.linux_isolation_diagnostic()
    assert 'SYNTH_SECRET' not in diagnostic and '/private/path' not in diagnostic
    row = json.loads(diagnostic)
    assert row['status_error'] == {'type': 'ValueError', 'errno': None}
    assert row['ipv4_error'] == {'type': 'ValueError', 'errno': None}
    assert row['interfaces']['other_count'] == 1


def test_failed_nnp_attestation_cannot_fall_back_to_elevation(guard, isolated, monkeypatch):
    _proc, sysfs = isolated
    (sysfs / 'flags').write_text('0x9')
    def forbidden(*args):
        raise AssertionError('privileged runner selection reached under NoNewPrivs')
    monkeypatch.setattr(guard.os, 'access', forbidden)
    with pytest.raises(ValueError, match='inherited isolation attestation failed') as error:
        guard.linux_command(['synthetic'])
    row = json.loads(str(error.value).split(': ', 1)[1])
    assert row['no_new_privs'] == 1 and row['interfaces']['loopback_flags'] == 9
    assert row['failed_predicates'] == ['lo_down_loopback']


def test_diagnostic_io_errors_have_only_type_and_errno(guard, isolated):
    proc, _sysfs = isolated
    (proc / 'net/ipv6_route').unlink()
    row = json.loads(guard.linux_isolation_diagnostic())
    assert row['ipv6_error'] == {'type': 'FileNotFoundError', 'errno': 2}
    assert str(proc) not in json.dumps(row)


def test_exact_empty_ipv4_table_is_isolated_but_other_empty_like_text_is_not(guard, isolated, monkeypatch):
    proc, _sysfs = isolated
    route = proc / 'net/route'
    header = route.read_text()
    route.write_bytes(b'')
    assert guard.linux_isolated()
    diagnostic = json.loads(guard.linux_isolation_diagnostic())
    assert diagnostic['predicates']['routeheader_ok']
    assert diagnostic['failed_predicates'] == []
    for content in [b'\n', b' ', b'Iface\n', b'not a route header\n']:
        route.write_bytes(content)
        assert not guard.linux_isolated()
        assert not json.loads(guard.linux_isolation_diagnostic())['predicates']['routeheader_ok']
    route.write_text(header)
    assert guard.linux_isolated()
    route.unlink()
    assert not guard.linux_isolated()
    original = Path.read_text
    def unreadable(path, *args, **kwargs):
        if path == route:
            raise PermissionError(13, 'SYNTH_SECRET/private/path')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', unreadable)
    assert not guard.linux_isolated()
    diagnostic = guard.linux_isolation_diagnostic()
    assert 'SYNTH_SECRET' not in diagnostic
    assert json.loads(diagnostic)['ipv4_error'] == {'type': 'PermissionError', 'errno': 13}


def test_generic_pytest_socket_mock_is_not_accepted_as_egress_proof(monkeypatch):
    calls = []
    def mocked(handle, address):
        calls.append(address)
        raise OSError('synthetic pytest denial without kernel errno')
    monkeypatch.setattr(socket.socket, 'connect', mocked)
    with pytest.raises(AssertionError):
        _blocked()
    assert calls == [('192.0.2.1', 9)]


@pytest.mark.parametrize('outcome', ['none', 'refused', 'unavailable', 'timeout', 'connected'])
def test_case_diagnostics_keep_unproven_denials_rejected(monkeypatch, capsys, outcome):
    import errno

    class FakeSocket:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def settimeout(self, value):
            pass
        def connect(self, address):
            if outcome == 'none':
                raise OSError('SYNTH_SECRET/private/path')
            if outcome == 'refused':
                raise OSError(errno.ECONNREFUSED, 'SYNTH_SECRET/private/path')
            if outcome == 'unavailable':
                raise OSError(errno.EADDRNOTAVAIL, 'SYNTH_SECRET/private/path')
            if outcome == 'timeout':
                raise TimeoutError('SYNTH_SECRET/private/path')
    monkeypatch.setattr(socket, 'socket', lambda *a, **kw: FakeSocket())
    with pytest.raises(AssertionError):
        _blocked('python-child')
    output = capsys.readouterr().err
    assert 'SYNTH_SECRET' not in output and '/private/path' not in output
    events = [json.loads(line.removeprefix('MDBX_EGRESS ')) for line in output.splitlines()]
    assert all(event['phase'] == 'python-child' and event['case'] == 'doc-v4' for event in events)
    assert events[-1]['operation'] == 'connect'
    assert events[-1]['outcome'] == ('timeout' if outcome == 'timeout' else
                                     'connected' if outcome == 'connected' else 'error')


def test_diagnostic_collection_records_all_denials_without_accepting_them(monkeypatch, capsys):
    import errno

    class FakeSocket:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def settimeout(self, value):
            pass
        def connect(self, address):
            raise OSError(errno.EADDRNOTAVAIL, 'SYNTH_SECRET/private/path')
    monkeypatch.setattr(socket, 'socket', lambda *a, **kw: FakeSocket())
    records = _blocked('python-parent', collect=True)
    assert [row['case'] for row in records] == ['doc-v4', 'loopback-v4', 'doc-v6', 'loopback-v6']
    assert len(records) == 4 and all(row['code'] == 'EADDRNOTAVAIL' for row in records)
    assert not all(row['code'] in {'ENETUNREACH', 'EAFNOSUPPORT'} for row in records)
    assert 'SYNTH_SECRET' not in capsys.readouterr().err


def test_kernel_metadata_counts_only_and_preserves_unreadable_state(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'uname', lambda: SimpleNamespace(release='6.12.0-synthetic'))
    (tmp_path / 'net').mkdir()
    source = tmp_path / 'net/if_inet6'
    source.write_text('SYNTHETIC_PRIVATE_ADDRESS\n\nsecond synthetic address\n')
    row = _kernel_metadata(tmp_path)
    assert row == {'kernel_release': '6.12.0-synthetic', 'ipv6_address_read': True,
                   'ipv6_address_entries': 2}
    assert 'PRIVATE' not in json.dumps(row)
    source.unlink()
    row = _kernel_metadata(tmp_path)
    assert row['ipv6_address_read'] is False and 'ipv6_address_entries' not in row
    assert row['ipv6_address_error'] == {'type': 'FileNotFoundError', 'errno': 2}
    assert str(tmp_path) not in json.dumps(row)
