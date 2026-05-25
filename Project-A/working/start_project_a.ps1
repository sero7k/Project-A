param(
  [int]$Port = 0,
  [int]$GamePort = 7777,
  [ValidateSet("menus", "custom", "pregame", "core", "practice")]
  [string]$ServerPhase = "menus",
  [string]$Label = "start",
  [int]$Seconds = 0,
  [bool]$BorderlessFullscreen = $true,
  [int]$ResX = 0,
  [int]$ResY = 0,
  [switch]$ExclusiveFullscreen,
  [switch]$GameSocketObserver,
  [ValidateSet("none", "echo", "hex", "ares-hex", "packet-hex", "ares-packet-hex", "ares-empty-packet", "ares-stateless-challenge", "ares-stateless-challenge-exact-clean", "ares-stateless-challenge-exact-marker", "ares-stateless-repeat", "ares-stateless-bootstrap", "ares-stateless-sequence", "ares-stateless-burst")]
  [string]$GameSocketReply = "none",
  [string]$GameSocketReplyHex = "",
  [string]$StatelessSequence = "",
  [string[]]$ClientArg = @(),
  [string]$ExecCmds = "",
  [string]$ExtraLogCmds = "",
  [bool]$AutoAcceptFriends = $true,
  [switch]$ListenServer,
  # Multiplayer: start as listen-server host (binds port $GamePort)
  [switch]$MultiplayerHost,
  # Multiplayer: connect to an existing listen server at HOST:PORT
  [string]$ConnectServer = "",
  [int]$NumPlayers = 2,
  [string]$Map = "",
  [string]$Mode = "",
  [string]$Profile = "developer"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root "reverse-logs"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

if ($Port -eq 0) {
  $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $Listener.Start()
  $Port = [int]$Listener.LocalEndpoint.Port
  $Listener.Stop()
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Exe = Join-Path $Root "ShooterGame\Binaries\Win64\ShooterClient-Win64-Shipping.exe"
$Cwd = Split-Path -Parent $Exe
$RequestLog = Join-Path $Out "rnet_requests_$Label-$Stamp.jsonl"
$ClientLog = Join-Path $Out "rnet-$Label-$Stamp-client.log"
$ServerOut = Join-Path $Out "rnet-$Label-$Stamp-server.out.log"
$ServerErr = Join-Path $Out "rnet-$Label-$Stamp-server.err.log"
$GameSocketLog = Join-Path $Out "game_socket_$Label-$Stamp.jsonl"
$GameSocketOut = Join-Path $Out "game_socket_$Label-$Stamp.out.log"
$GameSocketErr = Join-Path $Out "game_socket_$Label-$Stamp.err.log"

function Quote-Arg([string]$Arg) {
  if ($Arg -eq "") {
    return '""'
  }
  if ($Arg -match '[\s"]') {
    return '"' + ($Arg -replace '([\\]*)"', '$1$1\"' -replace '([\\]+)$', '$1$1') + '"'
  }
  return $Arg
}

function Start-ExactProcess($File, [string[]]$Arguments, $WorkingDirectory, [hashtable]$Environment = @{}, $Stdout = "", $Stderr = "") {
  $Psi = [System.Diagnostics.ProcessStartInfo]::new()
  $Psi.FileName = $File
  $Psi.Arguments = ($Arguments | ForEach-Object { Quote-Arg $_ }) -join " "
  $Psi.WorkingDirectory = $WorkingDirectory
  $Psi.UseShellExecute = $false
  $Psi.CreateNoWindow = $true
  if ($Stdout) {
    $Psi.RedirectStandardOutput = $true
  }
  if ($Stderr) {
    $Psi.RedirectStandardError = $true
  }
  foreach ($Key in $Environment.Keys) {
    $Psi.EnvironmentVariables[$Key] = [string]$Environment[$Key]
  }
  $Process = [System.Diagnostics.Process]::new()
  $Process.StartInfo = $Psi
  [void]$Process.Start()
  if ($Stdout) {
    Register-ObjectEvent -InputObject $Process -EventName OutputDataReceived -Action {
      if ($EventArgs.Data) {
        Add-Content -LiteralPath $Event.MessageData -Value $EventArgs.Data
      }
    } -MessageData $Stdout | Out-Null
    $Process.BeginOutputReadLine()
  }
  if ($Stderr) {
    Register-ObjectEvent -InputObject $Process -EventName ErrorDataReceived -Action {
      if ($EventArgs.Data) {
        Add-Content -LiteralPath $Event.MessageData -Value $EventArgs.Data
      }
    } -MessageData $Stderr | Out-Null
    $Process.BeginErrorReadLine()
  }
  return $Process
}

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Game executable not found: $Exe"
}

$Server = $null
$Client = $null
$Observer = $null

try {
  # Remove old certs so server generates fresh ones each run
  Remove-Item -LiteralPath (Join-Path $Out "rnet_probe.crt") -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $Out "rnet_probe.key") -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $Out "rnet_probe_ca.crt") -ErrorAction SilentlyContinue

  if ($GameSocketObserver -and -not $ListenServer -and -not $MultiplayerHost) {
    $ObserverSeconds = if ($Seconds -gt 0) { $Seconds + 15 } else { 86400 }
    $ObserverArgs = @(
      "reverse_tools\game_socket_observer.py",
      "--port", [string]$GamePort,
      "--log", $GameSocketLog,
      "--seconds", [string]$ObserverSeconds,
      "--udp-reply", $GameSocketReply
    )
    if ($GameSocketReply -in @("hex", "ares-hex", "packet-hex", "ares-packet-hex")) {
      $ObserverArgs += @("--udp-reply-hex", $GameSocketReplyHex)
    }
    if ($GameSocketReply -eq "ares-stateless-sequence" -and $StatelessSequence) {
      $ObserverArgs += @("--stateless-sequence", $StatelessSequence)
    }
    $Observer = Start-ExactProcess "python" $ObserverArgs $Root @{} $GameSocketOut $GameSocketErr
    Start-Sleep -Milliseconds 500
    if ($Observer.HasExited) {
      throw "game socket observer exited early with code $($Observer.ExitCode); see $GameSocketErr"
    }
  }
  if ($ListenServer -or $MultiplayerHost) {
    Write-Host "LISTEN_SERVER=1 -- skipping game socket observer to free UDP port $GamePort for UE listen socket"
  }

  $ServerArgs = @(
    "ProjectA-server\Server\project_a_server.py",
    "--port", [string]$Port,
    "--log", $RequestLog,
    "--cert", "reverse-logs\rnet_probe.crt",
    "--key", "reverse-logs\rnet_probe.key",
    "--ca-cert", "reverse-logs\rnet_probe_ca.crt",
    "--phase", $ServerPhase,
    "--game-port", [string]$GamePort,
    "--allow-memory-db"
  )
  if ($MultiplayerHost) {
    $ServerArgs += "--multiplayer-host"
    $ServerArgs += @("--num-players", [string]$NumPlayers)
    if ($Map)     { $ServerArgs += @("--map", $Map) }
    if ($Mode)    { $ServerArgs += @("--mode", $Mode) }
    if ($Profile) { $ServerArgs += @("--profile", $Profile) }
  } elseif ($ConnectServer) {
    $ServerArgs += @("--connect-server", $ConnectServer)
    if ($Map)     { $ServerArgs += @("--map", $Map) }
    if ($Mode)    { $ServerArgs += @("--mode", $Mode) }
    if ($Profile) { $ServerArgs += @("--profile", $Profile) }
  }
  $Server = Start-ExactProcess "python" $ServerArgs $Root @{} $ServerOut $ServerErr
  Start-Sleep -Seconds 2
  if ($Server.HasExited) {
    throw "probe server exited early with code $($Server.ExitCode); see $ServerErr"
  }

  # Install CA cert into current-user Root store (no admin required)
  $CaCertPath = Join-Path $Root "reverse-logs\rnet_probe_ca.crt"
  if (Test-Path -LiteralPath $CaCertPath) {
    & certutil -user -delstore Root "Project A Local Probe CA" 2>&1 | Out-Null
    & certutil -user -addstore -f Root $CaCertPath 2>&1 | Out-Null
    Write-Host "CA cert installed to CurrentUser\Root"
  } else {
    Write-Host "WARNING: CA cert not found at $CaCertPath"
  }

  $EnvVars = @{
    "SSL_CERT_FILE" = $CaCertPath
    "CURL_CA_BUNDLE" = $CaCertPath
  }

  $LogCmds = "LogPlatformInitializerV2 VeryVerbose,LogHttp Warning,LogPartyManager VeryVerbose,LogPartyService VeryVerbose,LogPartyModel VeryVerbose,LogCustomGameManager VeryVerbose,LogCustomGameModel VeryVerbose,LogPlatformCommon VeryVerbose"
  if ($ExtraLogCmds) {
    $LogCmds = "$LogCmds,$ExtraLogCmds"
  }

  $DisplayArgs = @()
  if ($ExclusiveFullscreen) {
    $DisplayArgs += "-fullscreen"
  } elseif ($BorderlessFullscreen) {
    try {
      Add-Type -AssemblyName System.Windows.Forms
      $Bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
      if ($ResX -le 0) {
        $ResX = [int]$Bounds.Width
      }
      if ($ResY -le 0) {
        $ResY = [int]$Bounds.Height
      }
    } catch {
      if ($ResX -le 0) {
        $ResX = 1920
      }
      if ($ResY -le 0) {
        $ResY = 1080
      }
    }
    $DisplayArgs += @("-windowed", "-borderless", "-WindowedFullscreen", "-ResX=$ResX", "-ResY=$ResY", "-WinX=0", "-WinY=0")
  }

  $ClientArgs = @(
    "-minimum-platform-init"
  )
  if (-not $ListenServer -and -not $MultiplayerHost) {
    $ClientArgs += "-Port=$GamePort"
  }
  foreach ($Arg in $DisplayArgs) {
    $ClientArgs += $Arg
  }
  foreach ($Arg in $ClientArg) {
    if ($Arg) {
      $ClientArgs += $Arg
    }
  }
  $ClientArgs += @(
    "-remoting-auth-token=developer",
    "-remoting-app-port=$Port",
    "-config-endpoint=https://127.0.0.1:$Port",
    "-rso-endpoint=https://127.0.0.1:$Port",
    "-abslog=$ClientLog",
    "-LogCmds=$LogCmds"
  )
  if ($ExecCmds) {
    $ClientArgs += "-ExecCmds=$ExecCmds"
  }

  Write-Host "PROJECT_A_SERVER_PORT=$Port"
  Write-Host "PROJECT_A_GAME_PORT=$GamePort"
  Write-Host "PROJECT_A_SERVER_PHASE=$ServerPhase"
  if ($ListenServer -or $MultiplayerHost) {
    Write-Host "PROJECT_A_LISTEN_SERVER=1"
  }
  if ($MultiplayerHost) {
    Write-Host "PROJECT_A_MULTIPLAYER_HOST=1 PLAYERS=$NumPlayers PORT=$GamePort"
  }
  if ($ConnectServer) {
    Write-Host "PROJECT_A_CONNECT_SERVER=$ConnectServer"
  }
  if ($ExclusiveFullscreen) {
    Write-Host "PROJECT_A_DISPLAY_MODE=exclusive-fullscreen"
  } elseif ($BorderlessFullscreen) {
    Write-Host "PROJECT_A_DISPLAY_MODE=borderless-fullscreen ${ResX}x${ResY}"
  } else {
    Write-Host "PROJECT_A_DISPLAY_MODE=client-default"
  }
  Write-Host "PROJECT_A_AUTO_ACCEPT_FRIENDS=$AutoAcceptFriends"
  Write-Host "REQUEST_LOG=$RequestLog"
  Write-Host "CLIENT_LOG=$ClientLog"
  Write-Host "SERVER_OUT=$ServerOut"
  Write-Host "SERVER_ERR=$ServerErr"
  if ($GameSocketObserver) {
    Write-Host "GAME_SOCKET_LOG=$GameSocketLog"
    Write-Host "GAME_SOCKET_OUT=$GameSocketOut"
    Write-Host "GAME_SOCKET_ERR=$GameSocketErr"
    Write-Host "GAME_SOCKET_REPLY=$GameSocketReply"
  }
  if ($Seconds -gt 0) {
    Write-Host "RUN_SECONDS=$Seconds"
  } else {
    Write-Host "Press Ctrl+C in this window to stop the local server and game."
  }

  $Client = Start-ExactProcess $Exe $ClientArgs $Cwd $EnvVars
  $Started = Get-Date
  while ($true) {
    Start-Sleep -Seconds 2
    if ($Server.HasExited) {
      throw "probe server exited with code $($Server.ExitCode); see $ServerErr"
    }
    if ($Client.HasExited) {
      Write-Host "CLIENT_EXITED=True EXIT_CODE=$($Client.ExitCode)"
      break
    }
    if ($Seconds -gt 0 -and ((Get-Date) - $Started).TotalSeconds -ge $Seconds) {
      Write-Host "TIMER_EXPIRED=True"
      break
    }
  }
}
finally {
  foreach ($Process in @($Client, $Server, $Observer)) {
    if ($Process -and -not $Process.HasExited) {
      Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
  }
}
