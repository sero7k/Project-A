param(
  [string]$HostName = $env:PROJECTA_HOST,
  [int]$Port = $(if ($env:PROJECTA_PORT) { [int]$env:PROJECTA_PORT } else { 39001 }),
  [string]$DatabaseUrl = $(if ($env:PROJECTA_DATABASE_URL) { $env:PROJECTA_DATABASE_URL } elseif ($env:DATABASE_URL) { $env:DATABASE_URL } else { "" }),
  [switch]$AllowMemoryDb,
  [ValidateSet("menus", "custom", "pregame", "core", "practice")]
  [string]$Phase = "menus"
)

$ErrorActionPreference = "Stop"

$ServerRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ServerRoot

if (-not $HostName) {
  $HostName = "127.0.0.1"
}

$ServerArgs = @(
  "project_a_server.py",
  "--host", $HostName,
  "--port", [string]$Port,
  "--phase", $Phase,
  "--log", "logs/rnet_requests.jsonl",
  "--cert", "logs/rnet_probe.crt",
  "--key", "logs/rnet_probe.key",
  "--ca-cert", "logs/rnet_probe_ca.crt"
)

if ($DatabaseUrl) {
  $ServerArgs += @("--database-url", $DatabaseUrl)
}
if ($AllowMemoryDb) {
  $ServerArgs += "--allow-memory-db"
}

python @ServerArgs
