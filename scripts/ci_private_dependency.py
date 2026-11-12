"""Configure CI access to the single private ollama-client dependency."""
import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path


def main():
    private_key = os.environ.get("OLLAMA_CLIENT_DEPLOY_KEY", "")
    if not private_key:
        raise SystemExit("OLLAMA_CLIENT_DEPLOY_KEY is required for private dependency installation")
    directory = Path(os.environ["RUNNER_TEMP"]) / "mdbx-private-dependency"
    directory.mkdir(mode=0o700, exist_ok=True)
    key = directory / "key"
    key.write_text(private_key.rstrip() + "\n")
    key.chmod(0o600)
    # Fetch host keys over authenticated HTTPS certificate validation; never disable SSH host checks.
    request = urllib.request.Request("https://api.github.com/meta", headers={"User-Agent": "mdbx-ci"})
    with urllib.request.urlopen(request, timeout=20) as response:
        host_keys = json.load(response)["ssh_keys"]
    if not host_keys or not all(isinstance(value, str) and "\n" not in value for value in host_keys):
        raise SystemExit("GitHub did not return valid SSH host keys")
    known_hosts = directory / "known_hosts"
    known_hosts.write_text("".join("github.com " + value + "\n" for value in host_keys))
    ssh = "ssh -i " + shlex.quote(str(key)) + " -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=" + shlex.quote(str(known_hosts))
    subprocess.run(["git", "config", "--global", "core.sshCommand", ssh], check=True)
    subprocess.run(["git", "config", "--global", "url.ssh://git@github.com/mithudso/ollama-client.git.insteadOf", "https://github.com/mithudso/ollama-client.git"], check=True)


if __name__ == "__main__":
    main()
