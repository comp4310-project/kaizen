<#
.SYNOPSIS
Starts the Kaizen demo with one command: checks, installs, demo database, API and front end.

.DESCRIPTION
Run it from the repository root, in Windows PowerShell 5.1 or PowerShell 7:

    powershell -ExecutionPolicy Bypass -File scripts\demo.ps1

In order, it checks Python 3.12 or newer, Node 20.19 or newer and npm, looks for Ollama and
checks that the two ports are free. Then it creates backend\.venv and installs the back end
(skipped when backend\pyproject.toml has not changed since the last install), runs npm ci in
frontend (skipped when package-lock.json has not changed), builds work\demo.db if it is not
there yet, and starts uvicorn and Vite with their logs in work\logs. When both answer it
prints the address and the demo accounts and opens the browser. Ctrl+C stops both.

The password for the demo accounts is asked once, when the database is built. It is passed
to the build script through KAIZEN_DEMO_PASSWORD for that one process and never printed or
saved. Forgot it? Run again with -Fresh.

.PARAMETER Check
Run the checks only, change nothing, and exit. The exit code is 1 if any check failed.

.PARAMETER Fresh
Delete work\demo.db and build it again, which asks for a new password.

.PARAMETER Local
Use the local Ollama model for suggestions even when ANTHROPIC_API_KEY is set.

.PARAMETER LlmLabels
When the database is built, label the comments with the LLM instead of the TF-IDF baseline
(sets KAIZEN_LABEL_MODEL to the Ollama model unless hosted models are in use). Much slower
than the baseline. Has no effect when work\demo.db already exists, so pair it with -Fresh.

.PARAMETER ApiPort
Port for the API (uvicorn). Default 8000. The front end's /api proxy follows it.

.PARAMETER WebPort
Port for the front end (Vite). Default 5173.

.PARAMETER NoBrowser
Do not open the browser once the app is up.

.PARAMETER PasswordFile
For automated testing only. Reads the demo password from the first line of this file instead
of asking. Keep the file outside the repository and delete it afterwards.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Check

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Fresh
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Fresh,
    [switch]$Local,
    [switch]$LlmLabels,
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1, 65535)][int]$WebPort = 5173,
    [switch]$NoBrowser,
    [Parameter(DontShow)][string]$PasswordFile = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # the Invoke-WebRequest progress bar is very slow in 5.1

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Work = Join-Path $Root "work"
$Logs = Join-Path $Work "logs"
$Db = Join-Path $Work "demo.db"
$DbBuilding = Join-Path $Work "demo-building.db"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvStamp = Join-Path $Venv "kaizen-pyproject.sha256"
$NodeModules = Join-Path $Frontend "node_modules"
$NpmStamp = Join-Path $NodeModules ".kaizen-package-lock.sha256"
$OllamaModel = "qwen2.5:7b"
$StopMarker = "KAIZEN_DEMO_STOP"

$script:Failures = 0
$script:Children = @()
$script:SavedEnv = @{}

# ---------------------------------------------------------------- output

function Write-Ok([string]$Message) { Write-Host "ok    $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "warn  $Message" -ForegroundColor Yellow }
function Write-Step([string]$Message) { Write-Host "..    $Message" }
function Write-Info([string]$Message) { Write-Host "      $Message" }

# Prints the problem and the fix. With -Check it keeps going so every problem is listed;
# otherwise it stops the script.
function Stop-Demo([string]$Message, [string]$Fix) {
    Write-Host "FAIL  $Message" -ForegroundColor Red
    if ($Fix) { Write-Host "      Fix: $Fix" }
    $script:Failures++
    if (-not $Check) { throw $StopMarker }
}

# ---------------------------------------------------------------- helpers

# Windows PowerShell joins -ArgumentList with spaces and does not quote, so do it here.
function Join-Arguments([string[]]$Arguments) {
    $quoted = foreach ($a in $Arguments) {
        if ($a -match '[\s"]' -or $a -eq "") { '"' + ($a -replace '"', '\"') + '"' } else { $a }
    }
    return ($quoted -join " ")
}

# Runs a short native command and returns its exit code and output. Stderr is dropped, and
# a missing command gives code -1 instead of an error.
function Invoke-Quiet([string]$Exe, [string[]]$Arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $Exe @Arguments 2>$null
        $code = $LASTEXITCODE
    } catch {
        $out = $null
        $code = -1
    } finally {
        $ErrorActionPreference = $old
    }
    return [pscustomobject]@{ Code = $code; Output = (@($out) -join "`n").Trim() }
}

# Runs a long command with its output in work\logs\<Name>.log and <Name>.err.log.
function Invoke-Logged([string]$Exe, [string[]]$Arguments, [string]$WorkingDirectory, [string]$Name) {
    $out = Join-Path $Logs "$Name.log"
    $err = Join-Path $Logs "$Name.err.log"
    $p = Start-Process -FilePath $Exe -ArgumentList (Join-Arguments $Arguments) -WorkingDirectory $WorkingDirectory `
        -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $p.Handle  # keeps ExitCode readable after the process ends
    while (-not $p.WaitForExit(500)) { }
    return $p.ExitCode
}

function Get-Sha256([string]$Path) { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash }

function Read-Stamp([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    $text = Get-Content -LiteralPath $Path -Raw
    if ($null -eq $text) { return "" }
    return $text.Trim()
}

function Show-LogTail([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Write-Info "Last lines of $(Resolve-Path -LiteralPath $Path -Relative):"
        Get-Content -LiteralPath $Path -Tail 15 | ForEach-Object { Write-Info "  $_" }
    }
}

# Sets an environment variable for this script and the processes it starts, and remembers
# the old value so it can be put back. Running the script with .\scripts\demo.ps1 shares the
# caller's environment, so without this the variables would outlive the script.
function Set-DemoEnv([string]$Name, [string]$Value) {
    if (-not $script:SavedEnv.ContainsKey($Name)) {
        $script:SavedEnv[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
    }
    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Restore-DemoEnv {
    foreach ($name in @($script:SavedEnv.Keys)) {
        [Environment]::SetEnvironmentVariable($name, $script:SavedEnv[$name], "Process")
    }
    $script:SavedEnv = @{}
}

function Stop-Children {
    $stopped = $false
    foreach ($p in $script:Children) {
        if ($null -ne $p -and -not $p.HasExited) {
            # /T takes the whole tree: Vite starts its own helper processes.
            $null = Invoke-Quiet "taskkill.exe" @("/PID", "$($p.Id)", "/T", "/F")
            $stopped = $true
        }
    }
    if ($script:Children.Count -gt 0) {
        foreach ($p in $script:Children) { if ($null -ne $p) { $null = $p.WaitForExit(5000) } }
        if ($stopped) { Write-Host "Stopped the API and the front end." } else { Write-Host "The API and the front end have stopped." }
    }
    $script:Children = @()
}

function Test-Url([string]$Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

# ---------------------------------------------------------------- checks

function Find-Python {
    $candidates = @(@("py", "-3.12"), @("py", "-3"), @("python"), @("python3"))
    foreach ($c in $candidates) {
        $exe = $c[0]
        $pre = @($c | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $r = Invoke-Quiet $exe ($pre + @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"))
        if ($r.Code -ne 0 -or $r.Output -notmatch '^\d+\.\d+\.\d+$') { continue }
        if ([version]$r.Output -ge [version]"3.12") {
            return [pscustomobject]@{ Exe = $exe; Pre = $pre; Version = $r.Output; Label = ($c -join " ") }
        }
    }
    return $null
}

function Test-NodeVersion([version]$v) {
    # Vite 8 needs ^20.19.0 or >=22.12.0.
    if ($v.Major -eq 20) { return $v.Minor -ge 19 }
    if ($v.Major -eq 22) { return $v.Minor -ge 12 }
    return $v.Major -gt 22
}

function Get-PortOwner([int]$Port) {
    $conns = @()
    try { $conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop) } catch { $conns = @() }
    if ($conns.Count -gt 0) {
        $owner = $conns[0].OwningProcess
        $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { "unknown process" }
        return [pscustomobject]@{ Id = $owner; Name = $name }
    }
    # Get-NetTCPConnection is missing on some machines, so also try to listen on the port.
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $null
    } catch {
        return [pscustomobject]@{ Id = 0; Name = "unknown process" }
    } finally {
        if ($null -ne $listener) { $listener.Stop() }
    }
}

function Test-Port([int]$Port, [string]$What) {
    $owner = Get-PortOwner $Port
    if ($null -eq $owner) {
        Write-Ok "Port $Port is free ($What)"
        return
    }
    if ($owner.Id -gt 0) {
        $hint = if ($owner.Name -in @("python", "node", "uvicorn")) { " It may be an earlier demo that is still running." } else { "" }
        Stop-Demo "Port $Port ($What) is in use by $($owner.Name), PID $($owner.Id).$hint" `
            "close it with: Stop-Process -Id $($owner.Id)   or pick another port with -ApiPort / -WebPort"
    } else {
        Stop-Demo "Port $Port ($What) is in use." "close whatever is using it, or pick another port with -ApiPort / -WebPort"
    }
}

# Set to $true by Set-Models when Ollama has the model, so the build can name issues with it.
$script:OllamaReady = $false

# Decides which models the API (and an LLM-labelled build) will use, and sets them.
function Set-Models {
    if ($env:ANTHROPIC_API_KEY -and -not $Local) {
        Write-Ok "ANTHROPIC_API_KEY is set, so suggestions use the hosted models (add -Local to use Ollama)"
        return
    }
    $models = $null
    try {
        $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3
        $models = @($tags.models | ForEach-Object { $_.name })
    } catch {
        $models = $null
    }
    # Set even when Ollama is down, so starting Ollama later is enough, without a restart.
    Set-DemoEnv "KAIZEN_SUGGEST_MODEL" "ollama/$OllamaModel"
    if ($LlmLabels) { Set-DemoEnv "KAIZEN_LABEL_MODEL" "ollama/$OllamaModel" }
    if ($null -eq $models) {
        if ($LlmLabels -and $Fresh) {
            Stop-Demo "Ollama is not running, and -LlmLabels needs it to build the database." `
                "start the Ollama app (or run: ollama serve), then run this again"
        }
        Write-Warn "Ollama is not running at http://localhost:11434. Suggestions will not work until you start it."
        Write-Info "Fix: start the Ollama app, or run: ollama serve. The rest of the demo works without it."
    } elseif ($models -notcontains $OllamaModel) {
        Write-Warn "Ollama is running but does not have $OllamaModel. Suggestions will not work until it does."
        Write-Info "Fix: ollama pull $OllamaModel   (about 4.7 GB)"
    } else {
        Write-Ok "Ollama is running with $OllamaModel, suggestions and issue names use ollama/$OllamaModel"
        # Readable issue names ("Delayed discharge medications") instead of keyword lists.
        Set-DemoEnv "KAIZEN_NAME_MODEL" "ollama/$OllamaModel"
        $script:OllamaReady = $true
    }
}

# ---------------------------------------------------------------- steps

function Get-DemoPassword {
    if ($PasswordFile) {
        if (-not (Test-Path -LiteralPath $PasswordFile)) { Stop-Demo "Password file not found: $PasswordFile" "" }
        $text = Get-Content -LiteralPath $PasswordFile -Raw
        if ($null -eq $text) { $text = "" }
        $password = ($text -split "`r?`n")[0]
        if ($password.Length -lt 10) { Stop-Demo "The password file must start with a password of 10 or more characters." "" }
        return $password
    }
    Write-Info "Choose one password for demo-qi, demo-manager and demo-admin (10 or more characters)."
    Write-Info "It is not shown, printed or saved. If you forget it, run again with -Fresh."
    for ($i = 0; $i -lt 3; $i++) {
        $secure = Read-Host "      Password" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        if ($password.Length -ge 10) { return $password }
        Write-Warn "That is too short, it needs 10 or more characters."
    }
    Stop-Demo "No password of 10 or more characters was given." "run the script again"
}

function Install-Backend($python) {
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        if (Test-Path -LiteralPath $Venv) {
            Stop-Demo "backend\.venv exists but has no Scripts\python.exe (it may come from another computer or a broken install)." `
                "delete the backend\.venv folder and run this again"
        }
        Write-Step "Creating backend\.venv with Python $($python.Version)"
        $r = Invoke-Quiet $python.Exe ($python.Pre + @("-m", "venv", $Venv))
        if ($r.Code -ne 0) { Stop-Demo "Could not create backend\.venv." "run: $($python.Label) -m venv backend\.venv   and read the error" }
    }
    $hash = Get-Sha256 (Join-Path $Backend "pyproject.toml")
    if ((Read-Stamp $VenvStamp) -eq $hash) {
        Write-Ok "Back end already installed and pyproject.toml unchanged"
        return
    }
    Write-Step "Installing the back end into backend\.venv (first time takes a few minutes, log in work\logs\pip-install.log)"
    $code = Invoke-Logged $VenvPython @("-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]") $Backend "pip-install"
    if ($code -ne 0) {
        Show-LogTail (Join-Path $Logs "pip-install.err.log")
        Stop-Demo "pip install failed (exit code $code)." "read work\logs\pip-install.err.log; a network problem usually fixes itself on a second run"
    }
    Set-Content -LiteralPath $VenvStamp -Value $hash -Encoding ASCII
    Write-Ok "Back end installed"
}

function Install-Frontend([string]$npm) {
    $hash = Get-Sha256 (Join-Path $Frontend "package-lock.json")
    if ((Test-Path -LiteralPath $NodeModules) -and (Read-Stamp $NpmStamp) -eq $hash) {
        Write-Ok "Front end packages already installed and package-lock.json unchanged"
        return
    }
    Write-Step "Running npm ci in frontend (log in work\logs\npm-ci.log)"
    $code = Invoke-Logged $npm @("ci", "--no-audit", "--no-fund") $Frontend "npm-ci"
    if ($code -ne 0) {
        Show-LogTail (Join-Path $Logs "npm-ci.err.log")
        Stop-Demo "npm ci failed (exit code $code)." "read work\logs\npm-ci.err.log; if a file is locked, close editors and other terminals using frontend and run again"
    }
    Set-Content -LiteralPath $NpmStamp -Value $hash -Encoding ASCII
    Write-Ok "Front end packages installed"
}

function Build-Database {
    if ($Fresh -and (Test-Path -LiteralPath $Db)) {
        try { Remove-Item -LiteralPath $Db -Force }
        catch { Stop-Demo "Could not delete work\demo.db, something still has it open." "stop the running demo (Ctrl+C in its window) and run again" }
        Write-Ok "Deleted the old work\demo.db (-Fresh)"
    }
    if (Test-Path -LiteralPath $Db) {
        Write-Ok "Demo database work\demo.db exists (use -Fresh to rebuild it)"
        return
    }
    # Build under another name and rename at the end, so a build that fails or is stopped
    # halfway never leaves a demo.db that looks finished.
    if (Test-Path -LiteralPath $DbBuilding) { Remove-Item -LiteralPath $DbBuilding -Force }
    Write-Step "Building the demo database work\demo.db"
    $password = Get-DemoPassword
    $arguments = @((Join-Path $Backend "scripts\demo_data.py"), $DbBuilding)
    if ($LlmLabels) { $arguments += @("--labeller", "llm") }
    if ($script:OllamaReady) { $arguments += @("--llm-names") }
    Write-Info "Importing, de-identifying, labelling and grouping 2,300 synthetic comments, about two minutes."

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $VenvPython
    $psi.Arguments = Join-Arguments $arguments
    $psi.WorkingDirectory = $Backend
    $psi.UseShellExecute = $false
    # Only this child gets the password. It starts with a copy of this process's variables.
    $psi.EnvironmentVariables["KAIZEN_DEMO_PASSWORD"] = $password
    $password = $null
    $proc = [System.Diagnostics.Process]::Start($psi)
    $psi.EnvironmentVariables.Remove("KAIZEN_DEMO_PASSWORD")
    while (-not $proc.WaitForExit(500)) { }
    if ($proc.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $DbBuilding) { Remove-Item -LiteralPath $DbBuilding -Force -ErrorAction SilentlyContinue }
        Stop-Demo "Building the demo database failed (exit code $($proc.ExitCode))." "read the error above, then run again"
    }
    Move-Item -LiteralPath $DbBuilding -Destination $Db
    Write-Ok "Demo database built"
}

function Start-Child([string]$Name, [string]$Exe, [string[]]$Arguments, [string]$WorkingDirectory) {
    $p = Start-Process -FilePath $Exe -ArgumentList (Join-Arguments $Arguments) -WorkingDirectory $WorkingDirectory `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput (Join-Path $Logs "$Name.log") -RedirectStandardError (Join-Path $Logs "$Name.err.log")
    $null = $p.Handle
    $script:Children += $p
    return $p
}

function Start-App([string]$NodeExe) {
    Set-DemoEnv "KAIZEN_DATABASE_URL" ("sqlite:///" + ($Db -replace '\\', '/'))
    Set-DemoEnv "KAIZEN_INDEX_PATH" (Join-Path $Work "kaizen-passages.npz")
    Set-DemoEnv "KAIZEN_API_PORT" "$ApiPort"

    Write-Step "Starting the API on port $ApiPort and the front end on port $WebPort (logs in work\logs)"
    $api = Start-Child "api" $VenvPython @("-m", "uvicorn", "kaizen.api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", "$ApiPort") $Backend
    $vite = Join-Path $NodeModules "vite\bin\vite.js"
    $web = Start-Child "web" $NodeExe @($vite, "--port", "$WebPort", "--strictPort") $Frontend

    $apiUp = $false
    $webUp = $false
    $deadline = (Get-Date).AddSeconds(60)
    while (-not ($apiUp -and $webUp)) {
        if ($api.HasExited) {
            Show-LogTail (Join-Path $Logs "api.err.log")
            Stop-Demo "The API stopped while starting (exit code $($api.ExitCode))." "read work\logs\api.err.log"
        }
        if ($web.HasExited) {
            Show-LogTail (Join-Path $Logs "web.err.log")
            Show-LogTail (Join-Path $Logs "web.log")
            Stop-Demo "The front end stopped while starting (exit code $($web.ExitCode))." "read work\logs\web.log and web.err.log"
        }
        if ((Get-Date) -gt $deadline) {
            $which = if (-not $apiUp) { "The API" } else { "The front end" }
            Stop-Demo "$which did not answer within 60 seconds." "read the logs in work\logs, then run again"
        }
        if (-not $apiUp) { $apiUp = Test-Url "http://127.0.0.1:$ApiPort/units" }
        if (-not $webUp) { $webUp = Test-Url "http://localhost:$WebPort/" }
        if (-not ($apiUp -and $webUp)) { Start-Sleep -Milliseconds 500 }
    }
    if (-not (Test-Url "http://localhost:$WebPort/api/units")) {
        Stop-Demo "The front end is up but cannot reach the API through /api." "check that frontend\vite.config.ts reads KAIZEN_API_PORT, and read work\logs\web.log"
    }
    Write-Ok "API and front end are answering"
    return @($api, $web)
}

function Show-Running {
    $url = "http://localhost:$WebPort"
    Write-Host ""
    Write-Host "Kaizen is running at $url" -ForegroundColor Green
    Write-Host "API docs at http://localhost:$ApiPort/docs, logs in work\logs"
    Write-Host ""
    Write-Host "Log in with the password chosen when work\demo.db was built:"
    Write-Host "  demo-qi        QI staff, all units. Upload a CSV, correct labels, rename and merge issues,"
    Write-Host "                 draft suggestions and accept, edit or reject them."
    Write-Host "  demo-manager   Unit manager for 4B. Sees issues, comments and the comparison for 4B only,"
    Write-Host "                 and cannot change anything."
    Write-Host "  demo-admin     Everything demo-qi can do, plus creating accounts (POST /users in the API docs)."
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both."
    if (-not $NoBrowser) { Start-Process $url }
}

# ---------------------------------------------------------------- main

function Invoke-Demo {
    New-Item -ItemType Directory -Force -Path $Logs | Out-Null

    $git = Invoke-Quiet "git" @("-C", $Root, "rev-parse", "--abbrev-ref", "HEAD")
    if ($git.Code -eq 0 -and $git.Output -ne "main") {
        Write-Warn "You are on branch $($git.Output), not main. For the demo: git checkout main; git pull"
    }

    $python = Find-Python
    if ($null -eq $python) {
        Stop-Demo "Python 3.12 or newer was not found (tried py -3.12, py -3, python, python3)." `
            "install Python 3.12 from https://www.python.org/downloads/ with 'Add python.exe to PATH' ticked, then open a new terminal"
    } else {
        Write-Ok "Python $($python.Version) ($($python.Label))"
    }
    if ((Test-Path -LiteralPath $VenvPython)) {
        $r = Invoke-Quiet $VenvPython @("-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])")
        if ($r.Code -ne 0 -or $r.Output -notmatch '^\d+\.\d+\.\d+$' -or [version]$r.Output -lt [version]"3.12") {
            Stop-Demo "backend\.venv does not run Python 3.12 or newer." "delete the backend\.venv folder and run this again"
        }
    }

    $nodeExe = $null
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($null -eq $node) {
        Stop-Demo "Node was not found." "install Node 24 LTS from https://nodejs.org, then open a new terminal"
    } else {
        $nodeExe = $node.Source
        $v = (Invoke-Quiet $nodeExe @("--version")).Output.TrimStart("v")
        if ($v -notmatch '^\d+\.\d+\.\d+$' -or -not (Test-NodeVersion ([version]$v))) {
            Stop-Demo "Node $v is too old, Vite needs 20.19 or newer (22.12 or newer on the 22 line)." "install Node 24 LTS from https://nodejs.org, then open a new terminal"
        } else {
            Write-Ok "Node $v"
        }
    }

    # npm.cmd rather than npm, so the npm.ps1 shim and the execution policy are not involved.
    $npm = $null
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $npmCmd) {
        Stop-Demo "npm was not found." "it comes with Node: reinstall Node 24 LTS from https://nodejs.org"
    } else {
        $npm = $npmCmd.Source
        Write-Ok "npm $((Invoke-Quiet $npm @('--version')).Output)"
    }

    Set-Models
    Test-Port $ApiPort "API"
    Test-Port $WebPort "front end"

    if ($Check) {
        $pyHash = Get-Sha256 (Join-Path $Backend "pyproject.toml")
        if ((Test-Path -LiteralPath $VenvPython) -and (Read-Stamp $VenvStamp) -eq $pyHash) { Write-Ok "Back end installed and up to date" }
        else { Write-Info "Back end will be installed into backend\.venv on the next run (a few minutes)" }
        $lockHash = Get-Sha256 (Join-Path $Frontend "package-lock.json")
        if ((Test-Path -LiteralPath $NodeModules) -and (Read-Stamp $NpmStamp) -eq $lockHash) { Write-Ok "Front end packages installed and up to date" }
        else { Write-Info "npm ci will run in frontend on the next run" }
        if ((Test-Path -LiteralPath $Db) -and -not $Fresh) { Write-Ok "Demo database work\demo.db exists" }
        else { Write-Info "work\demo.db will be built on the next run (about two minutes, asks for a password)" }
        Write-Host ""
        if ($script:Failures -gt 0) {
            Write-Host "$($script:Failures) check(s) failed. Fix them before the demo." -ForegroundColor Red
        } else {
            Write-Host "All checks passed." -ForegroundColor Green
        }
        return
    }

    Install-Backend $python
    Install-Frontend $npm
    Build-Database
    $children = Start-App $nodeExe
    Show-Running
    while ($true) {
        foreach ($p in $children) {
            if ($p.HasExited) {
                $name = if ($p -eq $children[0]) { "api" } else { "web" }
                Show-LogTail (Join-Path $Logs "$name.err.log")
                Stop-Demo "The $(if ($name -eq 'api') { 'API' } else { 'front end' }) stopped (exit code $($p.ExitCode))." "read work\logs\$name.err.log, then run again"
            }
        }
        Start-Sleep -Seconds 1
    }
}

$exitCode = 0
try {
    Invoke-Demo
    if ($script:Failures -gt 0) { $exitCode = 1 }
} catch {
    if ($_.Exception.Message -ne $StopMarker) {
        Write-Host "FAIL  Unexpected error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host $_.ScriptStackTrace
    }
    $exitCode = 1
} finally {
    # Runs on Ctrl+C too.
    Stop-Children
    Restore-DemoEnv
}
exit $exitCode
