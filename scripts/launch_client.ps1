param(
  [int]$Port = 0,
  [int]$GamePort = 7777,
  [string]$ClientExe = "",
  [ValidateSet("menus", "custom", "pregame", "core", "practice")]
  [string]$ServerPhase = "menus",
  [string]$Label = "start",
  [int]$Seconds = 0,
  [bool]$BorderlessFullscreen = $true,
  [int]$ResX = 0,
  [int]$ResY = 0,
  [switch]$ExclusiveFullscreen,
  [switch]$UEGameServer,
  [switch]$GameSocketObserver,
  [switch]$NoGameSocket,
  [ValidateSet("none", "echo", "hex", "ares-hex", "packet-hex", "ares-packet-hex", "ares-empty-packet", "ares-stateless-challenge", "ares-stateless-challenge-exact-clean", "ares-stateless-challenge-exact-marker", "ares-stateless-repeat", "ares-stateless-bootstrap", "ares-stateless-sequence", "ares-stateless-burst", "ares-handshake")]
  [string]$GameSocketReply = "none",
  [string]$GameSocketReplyHex = "",
  [string]$StatelessSequence = "",
  [string]$HandshakeFinalSequence = "",
  [string[]]$ClientArg = @(),
  [string]$ExecCmds = "",
  [string]$ExtraLogCmds = "",
  [bool]$AutoAcceptFriends = $false,
  [string]$AccountKey = "",
  [string]$RiotName = "DevPlayer",
  [string]$TagLine = "LOCAL",
  [switch]$MemoryDb,
  [string]$DatabaseUrl = "",
  [switch]$NoDbMigrate,
  [switch]$ResetState,
  [int]$MatchmakingDelayMs = 0,
  [switch]$PatchClientCerts
)

$ErrorActionPreference = "Stop"

function Split-RiotId([string]$Raw, [string]$DefaultName, [string]$DefaultTag) {
  if ($null -eq $Raw) { $Raw = "" }
  $Value = $Raw.Trim().Trim('"').Trim("'").Trim()
  if (-not $Value) {
    return @{ Name = $DefaultName; Tag = $DefaultTag }
  }
  if ($Value -match "#") {
    $Parts = $Value.Split("#", 2)
    $Name = $Parts[0].Trim().Trim('"').Trim("'").Trim()
    $Tag = ""
    if ($Parts.Count -gt 1) {
      $Tag = $Parts[1].Trim().Trim('"').Trim("'").Trim()
    }
    if (-not $Name) { $Name = $DefaultName }
    if (-not $Tag) { $Tag = $DefaultTag }
    return @{ Name = $Name; Tag = $Tag }
  }
  return @{ Name = $Value; Tag = $DefaultTag }
}

function Normalize-AccountKey([string]$Raw) {
  if ($null -eq $Raw) { $Raw = "" }
  $Value = $Raw.Trim().ToLowerInvariant()
  $Value = [regex]::Replace($Value, "[^a-z0-9_.@-]+", "-").Trim("-", ".", "_")
  if (-not $Value) { return "developer" }
  return $Value
}

$EnvRiotId = if ($env:PROJECT_A_RIOT_ID) { [string]$env:PROJECT_A_RIOT_ID } else { "" }
if ($EnvRiotId -and -not $PSBoundParameters.ContainsKey("RiotName") -and -not $PSBoundParameters.ContainsKey("TagLine")) {
  $ParsedRiotId = Split-RiotId $EnvRiotId $RiotName $TagLine
  $RiotName = $ParsedRiotId.Name
  $TagLine = $ParsedRiotId.Tag
} elseif ($RiotName -match "#" -and (-not $PSBoundParameters.ContainsKey("TagLine") -or -not $TagLine)) {
  $ParsedRiotId = Split-RiotId $RiotName $RiotName $TagLine
  $RiotName = $ParsedRiotId.Name
  $TagLine = $ParsedRiotId.Tag
} else {
  $RiotName = $RiotName.Trim().Trim('"').Trim("'").Trim()
  $TagLine = $TagLine.Trim().Trim('"').Trim("'").Trim()
  if (-not $RiotName) { $RiotName = "DevPlayer" }
  if (-not $TagLine) { $TagLine = "LOCAL" }
}

if (-not $AccountKey) {
  $AccountKey = Normalize-AccountKey "$RiotName-$TagLine"
} else {
  $AccountKey = Normalize-AccountKey $AccountKey
}

if ((Split-Path -Leaf $PSScriptRoot) -eq "scripts") {
  $Root = Split-Path -Parent $PSScriptRoot
} else {
  $Root = $PSScriptRoot
}
$ServerScript = Join-Path $Root "Server\project_a_server.py"
if (-not (Test-Path -LiteralPath $ServerScript)) {
  throw "Server script not found: $ServerScript"
}
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
  $PythonExe = $VenvPython
} else {
  $PythonExe = "python"
}
$Out = Join-Path $Root "reverse-logs"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$EffectiveDatabaseUrl = ""
if ($DatabaseUrl) {
  $EffectiveDatabaseUrl = $DatabaseUrl
} elseif ($env:PROJECTA_DATABASE_URL) {
  $EffectiveDatabaseUrl = $env:PROJECTA_DATABASE_URL
} elseif ($env:DATABASE_URL) {
  $EffectiveDatabaseUrl = $env:DATABASE_URL
}
if (-not $MemoryDb -and -not $EffectiveDatabaseUrl) {
  $MemoryDb = $true
}

if ($Port -eq 0) {
  $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $Listener.Start()
  $Port = [int]$Listener.LocalEndpoint.Port
  $Listener.Stop()
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $ClientExe -and $env:PROJECT_A_CLIENT_EXE) {
  $ClientExe = [string]$env:PROJECT_A_CLIENT_EXE
}
if (-not $ClientExe) {
  throw "Client executable not configured. Pass -ClientExe or set PROJECT_A_CLIENT_EXE."
}
$Exe = $ClientExe
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

function Resolve-ClientRoot([string]$ExecutablePath) {
  $ResolvedExe = (Resolve-Path -LiteralPath $ExecutablePath).Path
  $Current = Split-Path -Parent $ResolvedExe
  for ($i = 0; $i -lt 8; $i++) {
    if ((Test-Path -LiteralPath (Join-Path $Current "ShooterClient.exe")) -and (Test-Path -LiteralPath (Join-Path $Current "ShooterGame"))) {
      return $Current
    }
    if ((Split-Path -Leaf $Current) -ieq "Project A Valorant") {
      return $Current
    }
    $Parent = Split-Path -Parent $Current
    if (-not $Parent -or $Parent -eq $Current) { break }
    $Current = $Parent
  }
  return (Split-Path -Parent $ResolvedExe)
}

function Get-ClientCertBundlePaths([string]$Root) {
  $RelativePaths = @(
    "Certificates\cacert.pem",
    "Certificates\ThirdParty\cacert.pem",
    "Engine\Binaries\Win64\Certificates\cacert.pem",
    "Engine\Binaries\Win64\Certificates\ThirdParty\cacert.pem",
    "Engine\Content\Certificates\cacert.pem",
    "Engine\Content\Certificates\ThirdParty\cacert.pem",
    "ShooterGame\Binaries\Win64\Certificates\cacert.pem",
    "ShooterGame\Binaries\Win64\Certificates\ThirdParty\cacert.pem",
    "ShooterGame\Content\Certificates\cacert.pem",
    "ShooterGame\Content\Certificates\ThirdParty\cacert.pem"
  )
  return $RelativePaths | ForEach-Object { Join-Path $Root $_ }
}

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Game executable not found: $Exe. Pass -ClientExe or set PROJECT_A_CLIENT_EXE."
}
$Exe = (Resolve-Path -LiteralPath $Exe).Path
$Cwd = Split-Path -Parent $Exe
$ClientRoot = Resolve-ClientRoot $Exe

$Server = $null
$Client = $null
$Observer = $null

try {
  if ($UEGameServer) {
    $GameSocketObserver = $true
    if ($GameSocketReply -eq "none") {
      $GameSocketReply = "ares-handshake"
    }
    if (-not $HandshakeFinalSequence) {
      $HandshakeFinalSequence = "52"
    }
  }
  if (-not $NoGameSocket -and -not $GameSocketObserver -and $GameSocketReply -eq "none") {
    $GameSocketObserver = $true
    $GameSocketReply = "ares-stateless-challenge-exact-clean"
  }
  if ($GameSocketObserver) {
    $ObserverSeconds = if ($Seconds -gt 0) { $Seconds + 15 } else { 86400 }
    $GameSocketScript = if ($UEGameServer) { "Server\ue_game_server.py" } else { "Server\game_socket.py" }
    $ObserverArgs = @(
      $GameSocketScript,
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
    if ($GameSocketReply -eq "ares-handshake" -and $HandshakeFinalSequence) {
      $ObserverArgs += @("--handshake-final-sequence", $HandshakeFinalSequence)
    }
    $Observer = Start-ExactProcess $PythonExe $ObserverArgs $Root @{} $GameSocketOut $GameSocketErr
    Start-Sleep -Milliseconds 500
    if ($Observer.HasExited) {
      throw "game socket observer exited early with code $($Observer.ExitCode); see $GameSocketErr"
    }
  }

  $ServerArgs = @(
    $ServerScript,
    "--port", [string]$Port,
    "--log", $RequestLog,
    "--cert", "reverse-logs\rnet_probe.crt",
    "--key", "reverse-logs\rnet_probe.key",
    "--ca-cert", "reverse-logs\rnet_probe_ca.crt",
    "--phase", $ServerPhase,
    "--game-port", [string]$GamePort,
    "--account-key", $AccountKey,
    "--riot-name", $RiotName,
    "--tag-line", $TagLine,
    "--matchmaking-delay-ms", [string]$MatchmakingDelayMs
  )
  if ($MemoryDb) {
    $ServerArgs += "--allow-memory-db"
  }
  if ($EffectiveDatabaseUrl) {
    $ServerArgs += @("--database-url", $EffectiveDatabaseUrl)
  }
  if ($NoDbMigrate) {
    $ServerArgs += "--no-db-migrate"
  }
  if ($ResetState) {
    $ServerArgs += "--reset-state"
  }
  if ($AutoAcceptFriends) {
    $ServerArgs += "--auto-accept-friend-requests"
  }
  $ServerEnv = @{}
  if ($EffectiveDatabaseUrl) {
    $ServerEnv["PROJECTA_DATABASE_URL"] = $EffectiveDatabaseUrl
  }
  $Server = Start-ExactProcess $PythonExe $ServerArgs $Root $ServerEnv $ServerOut $ServerErr
  Start-Sleep -Seconds 2
  if ($Server.HasExited) {
    throw "probe server exited early with code $($Server.ExitCode); see $ServerErr"
  }

  $LocalCaPath = Join-Path $Root "reverse-logs\rnet_probe_ca.crt"
  if ($PatchClientCerts) {
    $LocalCaText = (Get-Content -LiteralPath $LocalCaPath -Raw).Trim()
    $LocalCaSubject = "CN=Project A Local Probe CA"
    function Remove-ProjectALocalCa([string]$PemText) {
      $KeptBlocks = New-Object System.Collections.Generic.List[string]
      $Blocks = [regex]::Matches($PemText, "-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----")
      foreach ($BlockMatch in $Blocks) {
        $Block = $BlockMatch.Value
        $IsLocalCa = $false
        try {
          $Base64 = $Block `
            -replace "-----BEGIN CERTIFICATE-----", "" `
            -replace "-----END CERTIFICATE-----", "" `
            -replace "\s", ""
          $Cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new([Convert]::FromBase64String($Base64))
          $IsLocalCa = ($Cert.Subject -eq $LocalCaSubject)
        } catch {
          $IsLocalCa = $false
        }
        if (-not $IsLocalCa) {
          $KeptBlocks.Add($Block.Trim())
        }
      }
      if ($Blocks.Count -eq 0) {
        return $PemText.TrimEnd()
      }
      return ($KeptBlocks -join "`r`n`r`n")
    }
    Write-Host "PATCH_CLIENT_CERT_ROOT=$ClientRoot"
    $PatchedBundles = 0
    $DiscoveredBundles = @(Get-ChildItem -LiteralPath $ClientRoot -Recurse -Filter "cacert.pem" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    $CandidateBundles = @(Get-ClientCertBundlePaths $ClientRoot)
    $BundlePaths = @($DiscoveredBundles + $CandidateBundles | Where-Object { $_ } | Sort-Object -Unique)
    foreach ($BundlePath in $BundlePaths) {
      try {
        $CreatedBundle = $false
        if (-not (Test-Path -LiteralPath $BundlePath)) {
          $BundleDir = Split-Path -Parent $BundlePath
          New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
          Set-Content -LiteralPath $BundlePath -Value ($LocalCaText + "`r`n") -NoNewline -Encoding ascii -ErrorAction Stop
          $CreatedBundle = $true
        }
        $BundleText = Get-Content -LiteralPath $BundlePath -Raw -ErrorAction Stop
        $BundleText = Remove-ProjectALocalCa $BundleText
        if ($BundleText -notlike "*$LocalCaText*") {
          $Backup = "$BundlePath.bak-local-ca"
          if (-not $CreatedBundle -and -not (Test-Path -LiteralPath $Backup)) {
            Copy-Item -LiteralPath $BundlePath -Destination $Backup -ErrorAction Stop
          }
          Set-Content -LiteralPath $BundlePath -Value ($BundleText.TrimEnd() + "`r`n`r`n" + $LocalCaText + "`r`n") -NoNewline -Encoding ascii -ErrorAction Stop
        }
        $PatchedBundles += 1
        Write-Host "PATCHED_CLIENT_CERT=$BundlePath"
      } catch {
        throw "failed to patch client certificate bundle ${BundlePath}: $($_.Exception.Message)"
      }
    }
  }

  $ClientCaCert = Join-Path $env:TEMP "project_a_rnet_probe_ca.crt"
  Copy-Item -LiteralPath $LocalCaPath -Destination $ClientCaCert -Force
  $EnvVars = @{
    "SSL_CERT_FILE" = $ClientCaCert
    "CURL_CA_BUNDLE" = $ClientCaCert
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
    "-minimum-platform-init",
    "-n.VerifyPeer=0",
    "-Port=$GamePort"
  )
  foreach ($Arg in $DisplayArgs) {
    $ClientArgs += $Arg
  }
  foreach ($Arg in $ClientArg) {
    if ($Arg) {
      $ClientArgs += $Arg
    }
  }
  $ClientArgs += @(
    "-remoting-auth-token=$RiotName#$TagLine",
    "-remoting-app-port=$Port",
    "-config-endpoint=http://127.0.0.1:$Port",
    "-rso-endpoint=http://127.0.0.1:$Port",
    "-abslog=$ClientLog",
    "-LogCmds=$LogCmds"
  )
  if ($ExecCmds) {
    $ClientArgs += "-ExecCmds=$ExecCmds"
  }

  Write-Host "PROJECT_A_SERVER_PORT=$Port"
  Write-Host "PROJECT_A_GAME_PORT=$GamePort"
  Write-Host "PROJECT_A_SERVER_PHASE=$ServerPhase"
  Write-Host "PROJECT_A_CLIENT_ROOT=$ClientRoot"
  Write-Host "PROJECT_A_ACCOUNT_KEY=$AccountKey"
  Write-Host "PROJECT_A_RIOT_ID=$RiotName#$TagLine"
  Write-Host "PROJECT_A_MEMORY_DB=$MemoryDb"
  Write-Host "PROJECT_A_DATABASE_URL=$EffectiveDatabaseUrl"
  Write-Host "PROJECT_A_MATCHMAKING_DELAY_MS=$MatchmakingDelayMs"
  Write-Host "PROJECT_A_PATCH_CLIENT_CERTS=$PatchClientCerts"
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
    if ($UEGameServer) {
      Write-Host "UE_GAME_SERVER=True"
    }
    Write-Host "GAME_SOCKET_LOG=$GameSocketLog"
    Write-Host "GAME_SOCKET_OUT=$GameSocketOut"
    Write-Host "GAME_SOCKET_ERR=$GameSocketErr"
    Write-Host "GAME_SOCKET_REPLY=$GameSocketReply"
    if ($HandshakeFinalSequence) {
      Write-Host "GAME_SOCKET_HANDSHAKE_FINAL_SEQUENCE=$HandshakeFinalSequence"
    }
  } elseif ($NoGameSocket) {
    Write-Host "GAME_SOCKET_DISABLED=True"
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
