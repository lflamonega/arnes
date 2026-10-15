$ErrorActionPreference = "Stop"

try {
    $pythonVersion = & python --version 2>&1
} catch {
    Write-Host "Python 3.11 o superior no encontrado."
    Write-Host "Instalalo con: winget install Python.Python.3.11"
    exit 1
}

if (-not ($pythonVersion -match "Python (\d+)\.(\d+)")) {
    Write-Host "Python 3.11 o superior no encontrado."
    Write-Host "Instalalo con: winget install Python.Python.3.11"
    exit 1
}
$major = [int]$Matches[1]
$minor = [int]$Matches[2]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Host "Se requiere Python 3.11 o superior (detectado: $major.$minor)."
    Write-Host "Instalalo con: winget install Python.Python.3.11"
    exit 1
}

if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
    python -m pip install --user pipx
    python -m pipx ensurepath
}

$pipxList = pipx list 2>&1
if ($pipxList -match "arnes") {
    pipx upgrade arnes
} else {
    pipx install git+https://github.com/lflamonega/arnes.git
}

$arnesCmd = Get-Command arnes -ErrorAction SilentlyContinue
if (-not $arnesCmd) {
    Write-Host "Error: arnes no quedo disponible en PATH."
    exit 1
}
& arnes --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: arnes --version fallo."
    exit 1
}

Write-Host "arnes v0.0.1 instalado. Ejecuta 'arnes' para comenzar."
