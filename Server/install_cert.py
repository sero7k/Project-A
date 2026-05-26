#!/usr/bin/env python3
"""Remove all stale Project-A CA certs then install the current one."""
import subprocess, sys, tempfile, os
from pathlib import Path

CA_CERT = Path(__file__).parent / "logs" / "rnet_probe_ca.crt"

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, shell=True)

# Write a temp PS1 file to avoid quoting hell
ps_script = r"""
foreach ($store in @('Cert:\LocalMachine\Root', 'Cert:\CurrentUser\Root')) {
    Write-Host "  Checking $store"
    $certs = Get-ChildItem $store | Where-Object {
        $_.Subject -like '*Project A*' -or $_.Issuer -like '*Project A*'
    }
    foreach ($c in $certs) {
        Write-Host "  Removing: $($c.Thumbprint)  $($c.Subject)"
        $c | Remove-Item
    }
}
Write-Host "  Done removing."
"""
tmp_ps1 = Path(tempfile.gettempdir()) / "remove_project_a_certs.ps1"
tmp_ps1.write_text(ps_script, encoding="utf-8")

print("  Removing stale Project A CA certs via PowerShell...")
r = run(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{tmp_ps1}"')
print(r.stdout.strip() if r.stdout.strip() else "  (no output)")
if r.returncode != 0:
    print("  WARNING: PowerShell removal error:", r.stderr.strip())

tmp_ps1.unlink(missing_ok=True)

print(f"  Installing: {CA_CERT}")
r = run(f'certutil -addstore -f Root "{CA_CERT}"')
if r.returncode != 0:
    print("  ERROR installing cert:", r.stderr or r.stdout)
    sys.exit(1)

print("  Installing into current-user Root too...")
r_user = run(f'certutil -user -addstore -f Root "{CA_CERT}"')
if r_user.returncode != 0:
    print("  ERROR installing user cert:", r_user.stderr or r_user.stdout)
    sys.exit(1)

print("  CA cert installed OK")

# Verify
r2 = run(r'certutil -store Root "Project A Local Probe CA"')
import re
thumbprints = re.findall(r"Cert Hash\(sha1\)\s*:\s*([0-9a-fA-F ]+)", r2.stdout)
count = len(thumbprints)
print(f"  Certs now in local-machine store with that name: {count}")
if count != 1:
    print("  WARNING: Expected exactly 1 cert, got", count)

r3 = run(r'certutil -user -store Root "Project A Local Probe CA"')
user_thumbprints = re.findall(r"Cert Hash\(sha1\)\s*:\s*([0-9a-fA-F ]+)", r3.stdout)
user_count = len(user_thumbprints)
print(f"  Certs now in current-user store with that name: {user_count}")
if user_count != 1:
    print("  WARNING: Expected exactly 1 current-user cert, got", user_count)
