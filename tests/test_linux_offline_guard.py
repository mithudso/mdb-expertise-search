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


def _blocked():
    import errno

    for address in [('192.0.2.1', 9), ('127.0.0.1', 9),
                    ('2001:db8::1', 9), ('::1', 9)]:
        family = socket.AF_INET6 if ':' in address[0] else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as handle:
                handle.settimeout(1)
                handle.connect(address)
        except OSError as error:
            assert error.errno in {errno.ENETUNREACH, errno.EAFNOSUPPORT}, error
        else:
            raise AssertionError('synthetic documentation-address connection escaped')


def _egress_probe():
    import inspect

    probe = ('import errno,json,os,socket,subprocess,sys\n' +
             inspect.getsource(_blocked) + '\n_blocked()\n')
    child = 'import socket\n' + inspect.getsource(_blocked) + '\n_blocked()\n'
    node = """
const net = require('node:net'), cp = require('node:child_process');
async function blocked(host, family) {
  await new Promise((resolve, reject) => {
    const socket = net.createConnection({host, port: 9, family});
    socket.setTimeout(1000);
    socket.on('connect', () => { socket.destroy(); reject(Error('escaped')); });
    socket.on('timeout', () => { socket.destroy(); reject(Error('unexpected timeout')); });
    socket.on('error', error => {
      if (['ENETUNREACH', 'EAFNOSUPPORT'].includes(error.code)) resolve();
      else reject(error);
    });
  });
}
(async () => {
  await blocked('192.0.2.1', 4);
  await blocked('127.0.0.1', 4);
  await blocked('2001:db8::1', 6);
  await blocked('::1', 6);
  const child = cp.spawnSync(process.argv[1], ['-c', process.argv[2]], {stdio: 'inherit'});
  if (child.status !== 0) throw Error('Python descendant failed');
})().catch(error => { console.error(error.code || error.message); process.exitCode=1; });
"""
    probe += ('subprocess.run(["node","-e",' + repr(node) + ',sys.executable,' + repr(child) +
              '],check=True,timeout=10)\n'
              'print(json.dumps({"home":os.environ["HOME"],"root":os.environ["MDBX_TEST_ISOLATION_ROOT"]}))\n')
    return probe, node


def test_egress_probe_compiles_before_linux_execution():
    probe, _node = _egress_probe()
    compile(probe, '<Linux descendant proof>', 'exec')


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='actual Linux namespace proof')
def test_actual_linux_guard_is_inherited_by_python_and_node(tmp_path):
    import shutil

    guard = module()
    # Running this test outside the offline launcher fails before opening sockets.
    assert guard.linux_isolated(), guard.linux_isolation_diagnostic()
    assert shutil.which('node'), 'the maintained CI setup supplies Node'
    _blocked()
    probe, _node = _egress_probe()
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/offline_test.py'), '--',
                             sys.executable, '-c', probe],
                            capture_output=True, text=True, check=True, timeout=30)
    row = json.loads(result.stdout)
    assert Path(row['home']) == Path(row['root']) / 'home'
    assert not Path(row['root']).exists()


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
