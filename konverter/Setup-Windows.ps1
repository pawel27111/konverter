param(
    [string]$Distro = "Ubuntu-24.04",
    [switch]$PrerequisitesOnly
)
$ErrorActionPreference = "Stop"
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq "ARM64") {
    throw "Konverter benoetigt Windows x64. Windows ARM wird noch nicht unterstuetzt."
}
if ($Distro -notmatch '^[a-zA-Z0-9_.-]+$' -or $Distro.StartsWith('-')) {
    throw "Ungueltiger WSL-Verteilungsname."
}
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
$installed = @()
if ($wsl) {
    try {
        $installed = @((& wsl.exe --list --quiet 2>$null) -replace "`0", "" | ForEach-Object { $_.Trim() })
    } catch {
        # A fresh WSL installation may report that no distribution is registered yet.
        $installed = @()
    }
}
if (-not $wsl -or $installed -notcontains $Distro) {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        Write-Host "Windows fragt nach Administratorrechten fuer die WSL-Installation."
        $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Distro', $Distro)
        if ($PrerequisitesOnly) { $arguments += '-PrerequisitesOnly' }
        $child = Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
        exit $child.ExitCode
    }
    Write-Host "Installiere WSL2 und $Distro. Ein Windows-Neustart kann erforderlich sein."
    & wsl.exe --install --distribution $Distro --no-launch
    if ($LASTEXITCODE -ne 0) { throw "WSL-Installation nicht abgeschlossen (Exit $LASTEXITCODE). Nach einem erforderlichen Neustart erneut einrichten." }
}
$kernel = ((& wsl.exe --distribution $Distro --user root --exec uname -r 2>&1) -join "`n")
if ($LASTEXITCODE -ne 0) { throw "WSL startet noch nicht. Windows neu starten und Einrichtung wiederholen. $kernel" }
if ($kernel -notmatch '(?i)microsoft-standard|wsl2') {
    throw "Die Verteilung $Distro ist keine WSL2-Umgebung. Zuerst: wsl --set-version $Distro 2"
}
Write-Host "Installiere Linux-Voraussetzungen in $Distro ..."
& wsl.exe --distribution $Distro --user root --exec env DEBIAN_FRONTEND=noninteractive apt-get update
if ($LASTEXITCODE -ne 0) { throw "apt-get update fehlgeschlagen." }
& wsl.exe --distribution $Distro --user root --exec env DEBIAN_FRONTEND=noninteractive apt-get install -y python3 git ca-certificates libgomp1
if ($LASTEXITCODE -ne 0) { throw "Linux-Voraussetzungen konnten nicht installiert werden." }
Write-Host "WSL2 ist bereit."
if (-not $PrerequisitesOnly) {
    $cli = Join-Path (Split-Path $PSScriptRoot -Parent) "konverter-cli.exe"
    if (Test-Path $cli) {
        & $cli --distro $Distro setup
    } else {
        python -m konverter --distro $Distro setup
    }
    exit $LASTEXITCODE
}
exit 0
