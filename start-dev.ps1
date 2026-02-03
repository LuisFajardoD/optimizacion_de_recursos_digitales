$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venvPython = Join-Path $backend '.venv\Scripts\python.exe'

function Test-PortInUse {
  param([int]$Port)
  try {
    return @(Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop).Count -gt 0
  } catch {
    return $false
  }
}

function Test-CommandRunning {
  param([string]$Match)
  try {
    $procs = Get-CimInstance Win32_Process -ErrorAction Stop |
      Where-Object { $_.CommandLine -and $_.CommandLine -like "*$Match*" }
    return @($procs).Count -gt 0
  } catch {
    return $false
  }
}

if (-not (Test-Path $venvPython)) {
  Write-Host 'No se encontró .venv en backend\.venv. Crea el entorno virtual primero.' -ForegroundColor Red
  exit 1
}

Write-Host 'Instalando dependencias del backend...' -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $backend 'requirements.txt')

Write-Host 'Aplicando migraciones...' -ForegroundColor Cyan
# Evita prompts interactivos en entornos de arranque automático.
& $venvPython (Join-Path $backend 'manage.py') migrate --noinput

if (Test-PortInUse 8000) {
  Write-Host 'Backend ya está en ejecución (puerto 8000 ocupado).' -ForegroundColor Yellow
} else {
  Write-Host 'Levantando backend (Django)...' -ForegroundColor Green
  Start-Process -FilePath $venvPython -ArgumentList 'backend\manage.py runserver' -WorkingDirectory $root
}

if (Test-CommandRunning 'manage.py worker') {
  Write-Host 'Worker ya está en ejecución.' -ForegroundColor Yellow
} else {
  Write-Host 'Levantando worker local...' -ForegroundColor Green
  Start-Process -FilePath $venvPython -ArgumentList 'backend\manage.py worker' -WorkingDirectory $root
}

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
  Write-Host 'Instalando dependencias del frontend...' -ForegroundColor Cyan
  npm --prefix frontend install
}

if (Test-PortInUse 5173) {
  Write-Host 'Frontend ya está en ejecución (puerto 5173 ocupado).' -ForegroundColor Yellow
} else {
  Write-Host 'Levantando frontend (Vite)...' -ForegroundColor Green
  Start-Process -FilePath 'npm' -ArgumentList '--prefix frontend run dev -- --host 127.0.0.1 --port 5173' -WorkingDirectory $root
}

Write-Host 'Listo. Backend, worker y frontend en ejecución.' -ForegroundColor Green
