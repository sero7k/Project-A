$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Server = Join-Path $Root "tools\ares_udp_server.py"
$Log = Join-Path $Root "reverse-logs\ares_udp_server.jsonl"

python $Server --host 0.0.0.0 --port 7777 --log $Log
