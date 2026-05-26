$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Log = Join-Path $Root "reverse-logs\ares_udp_server.jsonl"

Push-Location $Root
try {
    python -m projecta.gameplay.ares_server --host 0.0.0.0 --port 7777 --log $Log
} finally {
    Pop-Location
}
