# Commit Roaster - Windows 11 development environment setup
#
# Run from the repository root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File setup\setup_windows.ps1
#
# What it does:
#   1. Prints this machine's specs (OS, CPU, RAM, disk) and saves them to setup\system-info.txt
#   2. Installs Python 3.12, Git and VS Code with winget (skips anything already installed)
#   3. Creates a .venv virtual environment and installs requirements.txt
#   4. Creates .env from .env.example if it does not exist yet

param(
    [switch]$SkipInstall,   # only report specs and build the venv
    [switch]$WithDocker     # also install Docker Desktop (only needed to self-host Dify)
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Install-IfMissing($command, $wingetId) {
    if (Get-Command $command -ErrorAction SilentlyContinue) {
        Write-Host "  $command already installed - skipping"
        return
    }
    Write-Host "  Installing $wingetId ..."
    winget install --id $wingetId -e --source winget --accept-package-agreements --accept-source-agreements
    Update-SessionPath
}

# ---------------------------------------------------------------------------
Write-Step "System specifications"
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"

$specs = [ordered]@{
    "OS"          = "$($os.Caption) (build $($os.BuildNumber), $($os.OSArchitecture))"
    "CPU"         = "$($cpu.Name.Trim()) - $($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads"
    "RAM"         = "{0:N1} GB" -f ($cs.TotalPhysicalMemory / 1GB)
    "Disk C:"     = "{0:N1} GB free of {1:N1} GB" -f ($disk.FreeSpace / 1GB), ($disk.Size / 1GB)
    "PowerShell"  = $PSVersionTable.PSVersion.ToString()
    "winget"      = if (Get-Command winget -ErrorAction SilentlyContinue) { (winget --version) } else { "NOT FOUND" }
}
$specs.GetEnumerator() | ForEach-Object { "{0,-11}: {1}" -f $_.Key, $_.Value } | Tee-Object -FilePath "setup\system-info.txt"

# ---------------------------------------------------------------------------
if (-not $SkipInstall) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget not found. Install 'App Installer' from the Microsoft Store, then re-run."
    }
    Write-Step "Installing tools with winget"
    Install-IfMissing "py"   "Python.Python.3.12"
    Install-IfMissing "git"  "Git.Git"
    Install-IfMissing "code" "Microsoft.VisualStudioCode"
    if ($WithDocker) { Install-IfMissing "docker" "Docker.DockerDesktop" }
}

# ---------------------------------------------------------------------------
Write-Step "Python virtual environment"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' not found. Open a new terminal (to refresh PATH) and re-run."
}
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

# ---------------------------------------------------------------------------
Write-Step "Configuration"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env - open it and paste your Dify app API key."
} else {
    Write-Host "  .env already exists - leaving it alone."
}

Write-Step "Versions"
& ".venv\Scripts\python.exe" --version
git --version

Write-Host "`nDone. Activate the environment with:  .venv\Scripts\Activate.ps1" -ForegroundColor Green
Write-Host "(If activation is blocked, run once:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)"
