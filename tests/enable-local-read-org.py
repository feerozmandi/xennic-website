#!/usr/bin/env python3
"""Offline tests with fake Docker and synthetic values; no real OAuth or Docker."""
import importlib.util
import os
import pty
import select
import signal
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

mod = load('scope_change', ROOT / 'scripts/enable-local-read-org.py')
config = load('oauth_config', ROOT / 'scripts/real-oauth-lab-config.py')


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.original = config.render_config('synthetic-client', 'synthetic-secret-token', '172.24.0.2', 'eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=')

    def test_only_scope_changes(self):
        new, client_id = mod.validate_config(self.original, '172.24.0.2')
        self.assertEqual(client_id, 'synthetic-client')
        self.assertEqual(new, self.original.replace('scope = "user:email"', 'scope = "user:email read:org"'))

    def test_rejects_policy_or_ip_changes(self):
        for value, ip in [(self.original.replace('github_users = ["feerozmandi"]', 'github_users = ["other"]'), '172.24.0.2'),
                          (self.original, '172.24.0.3'), (self.original, '8.8.8.8'),
                          (self.original.replace('scope = "user:email"', 'scope = "user:email read:org"'), '172.24.0.2')]:
            with self.subTest(ip=ip):
                with self.assertRaises((mod.LabError, ValueError)):
                    mod.validate_config(value, ip)

    def test_rolls_back_on_recreate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'oauth.toml'
            p.write_text(self.original)
            changed, _ = mod.validate_config(self.original, '172.24.0.2')
            seen = []
            def recreate():
                seen.append(p.read_text())
                if len(seen) == 1:
                    raise RuntimeError('synthetic failure')
            with self.assertRaisesRegex(mod.LabError, 'rolled back'):
                mod.apply_change(p, self.original, changed, recreate)
            self.assertEqual(seen, [changed, self.original])
            self.assertEqual(p.read_text(), self.original)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_rollback_failure_is_not_silenced(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'oauth.toml'
            p.write_text(self.original)
            def fail(): raise RuntimeError('synthetic failure')
            changed, _ = mod.validate_config(self.original, '172.24.0.2')
            with self.assertRaisesRegex(mod.LabError, 'rollback incomplete'):
                mod.apply_change(p, self.original, changed, fail)
            self.assertEqual(p.read_text(), self.original)


class FakeDockerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        home = Path(self.temp.name)
        self.lab = home / 'xennic-real-oauth-lab.UJInfVse'
        self.lab.mkdir(mode=0o700)
        result = subprocess.run(['git', '-C', str(ROOT), 'show',
                                 'c619bcf550cb58933268f93ed32174289e2f284b:scripts/real-oauth-local-lab.sh'],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest('pinned historical handoff unavailable')
        original = result.stdout
        template = re.search(r'cat > "\$ROOT/compose.yml" <<EOF\n(.*?)\nEOF\n', original, re.S).group(1) + '\n'
        for key, value in re.findall(r"^(CADDY|GATE|POSTGRES)='([^']+)'$", original, re.M):
            template = template.replace('$' + key, value)
        (self.lab / 'compose.yml').write_text(template.replace('\\${', '${'))
        pwd = 'b' * 64
        env = self.lab / 'lab.env'
        env.write_text(f'APP_IMAGE=sha256:{"a"*64}\nLAB_UID={os.getuid()}\nLAB_GID={os.getgid()}\n'
                       f'DB_PASSWORD={pwd}\nDATABASE_URL=postgresql://xennic_lab:{pwd}@postgres:5432/xennic_lab\n'
                       f'PAYLOAD_SECRET={"c"*64}\n')
        env.chmod(0o600)
        self.oauth = self.lab / 'oauth.toml'
        self.original = config.render_config('synthetic-client', 'synthetic-secret-token', '172.24.0.2', 'eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=')
        self.oauth.write_text(self.original)
        self.oauth.chmod(0o600)
        (self.lab / 'lab-root.crt').write_text('synthetic-certificate')
        bindir = home / 'bin'
        bindir.mkdir()
        docker = bindir / 'docker'
        docker.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
a=sys.argv[1:]; project='xennic-real-oauth-73c028764aa6'; state=Path(os.environ['FAKE_STATE']); lab=Path(os.environ['HOME'])/'xennic-real-oauth-lab.UJInfVse'
current=state.read_text() if state.exists() else '111111111111'
caddy='cccccccccccc'
if a[0]=='ps':
    print(caddy if any('service=caddy' in x for x in a) else current)
elif a[0]=='inspect':
    ident=a[1]; isgate=ident != caddy; name='gate' if isgate else 'caddy'
    image=('quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916' if isgate else 'caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e')
    bind={'443/tcp':[{'HostIp':'127.0.0.1','HostPort':'443'}]}
    names=['auth','egress'] if isgate else ['frontend','backend','auth']
    nets={project+'_'+x:{'IPAddress':'172.24.0.2' if x=='auth' else '172.25.0.2'} for x in names}
    mounts=[{'Destination':'/run/private/oauth.toml','Source':str(lab/'oauth.toml'),'RW':False}] if isgate else []
    print(json.dumps([{'State':{'Running':True},'Config':{'Image':image,'Labels':{'com.docker.compose.project':project,'com.docker.compose.service':name}},'HostConfig':{'LogConfig':{'Type':'none'},'PortBindings':{} if isgate else bind},'NetworkSettings':{'Ports':{} if isgate else bind,'Networks':nets},'Mounts':mounts}]))
elif a[0]=='compose':
    assert a[-8:] == ['up','-d','--no-deps','--force-recreate','--no-build','--pull','never','gate']
    assert all(k not in os.environ for k in ['APP_IMAGE','DATABASE_URL','DB_PASSWORD','PAYLOAD_SECRET','LAB_UID','LAB_GID','COMPOSE_FILE','COMPOSE_REMOVE_ORPHANS'])
    assert os.environ.get('COMPOSE_IGNORE_ORPHANS') == '1'
    fail=Path(os.environ['FAKE_FAIL_MARKER'])
    if os.environ.get('FAKE_FAIL_FIRST') == '1' and not fail.exists():
        fail.touch(); print('synthetic-secret-token', file=sys.stderr); raise SystemExit(1)
    state.write_text('222222222222' if current=='111111111111' else '333333333333')
else: raise SystemExit(1)
''')
        docker.chmod(0o700)
        curl = bindir / 'curl'
        curl.write_text("#!/bin/sh\n[ \"$1\" = '-q' ] || exit 1\nprintf 401\n")
        curl.chmod(0o700)
        self.env = dict(os.environ, HOME=str(home), PATH=str(bindir) + ':' + os.environ['PATH'],
                        DOCKER_HOST='unix:///synthetic', FAKE_STATE=str(home/'state'),
                        FAKE_FAIL_MARKER=str(home/'failed'), APP_IMAGE='shell-override',
                        DATABASE_URL='shell-override', DB_PASSWORD='shell-override',
                        PAYLOAD_SECRET='shell-override', LAB_UID='override', LAB_GID='override', COMPOSE_FILE='override',
                        COMPOSE_REMOVE_ORPHANS='1')
        self.env.pop('DOCKER_CONTEXT', None)

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, client_id=b'synthetic-client'):
        pid, master = pty.fork()
        if pid == 0:
            os.execve(sys.executable, [sys.executable, str(ROOT / 'scripts/enable-local-read-org.py')], self.env)
        output = bytearray()
        sent = False
        status = None
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .1)
                if ready:
                    try:
                        output.extend(os.read(master, 8192))
                    except OSError:
                        pass
                    if not sent and b'Client ID from the NEW independent test App settings (hidden): ' in output:
                        os.write(master, client_id + b'\n')
                        sent = True
                done, wait_status = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = wait_status
                    while select.select([master], [], [], 0)[0]:
                        try:
                            output.extend(os.read(master, 8192))
                        except OSError:
                            break
                    break
            else:
                self.fail('synthetic lab test timed out')
            self.assertTrue(sent, 'hidden client ID prompt was not displayed')
            self.assertNotIn(client_id, output)
            self.assertTrue(os.WIFEXITED(status))
            return subprocess.CompletedProcess([], os.WEXITSTATUS(status), bytes(output), b'')
        finally:
            if status is None:
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                except (ProcessLookupError, ChildProcessError):
                    pass
            os.close(master)

    def test_success_recreates_only_gate_and_does_not_print_secrets(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'PASS: lab gate restarted', result.stdout)
        self.assertNotIn(b'synthetic-secret-token', result.stdout + result.stderr)
        self.assertEqual(self.oauth.read_text(), self.original.replace('scope = "user:email"', 'scope = "user:email read:org"'))
        self.assertEqual(self.oauth.stat().st_mode & 0o777, 0o600)

    def test_failed_recreate_restores_original_without_printing_error_body(self):
        self.env['FAKE_FAIL_FIRST'] = '1'
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'original scope and lab gate were restored', result.stdout + result.stderr)
        self.assertNotIn(b'synthetic-secret-token', result.stdout + result.stderr)
        self.assertEqual(self.oauth.read_text(), self.original)


    def test_wrong_app_id_stops_without_changing_gate_or_config(self):
        result = self.invoke(b'synthetic-wrong-app')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'STOP:', result.stdout + result.stderr)
        self.assertEqual(self.oauth.read_text(), self.original)
        self.assertFalse((self.lab.parent / 'state').exists())


if __name__ == '__main__':
    unittest.main()
