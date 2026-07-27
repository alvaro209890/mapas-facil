# Fecha M9 no Windows: smoke Harmonia + checks + diff raster + pytest.
# Uso:
#   powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m9_windows.ps1
#   powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m9_windows.ps1 -Harmonia "C:\...\Harmonia"

param(
    [string]$Harmonia = "",
    [switch]$SemSmoke,
    [switch]$SemCommit
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$VenvPy = Join-Path $Repo "Fase_1_Desktop\nucleo\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPy)) {
    throw "venv do nucleo ausente. Rode: cd Fase_1_Desktop\nucleo; py -3.12 -m venv .venv; pip install -e .[dev]"
}

$OutDir = Join-Path $Repo "output"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$RelJson = Join-Path $OutDir "m9_fechamento_relatorio.json"
$smokeExit = $null

function Invoke-Step([string]$Titulo, [scriptblock]$Block) {
    Write-Host ""
    Write-Host "== $Titulo ==" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        throw "Falhou: $Titulo (exit $LASTEXITCODE)"
    }
}

if (-not $SemSmoke) {
    if (-not $Harmonia) {
        $candidatos = Get-ChildItem -Path (Join-Path $env:USERPROFILE "Downloads\Analise_de_area") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "Harmonia" } |
            Select-Object -First 1
        if ($candidatos) { $Harmonia = $candidatos.FullName }
    }
    if ($Harmonia -and (Test-Path -LiteralPath $Harmonia)) {
        Write-Host ""
        Write-Host "== Smoke M9 Harmonia ==" -ForegroundColor Cyan
        & $VenvPy ferramentas\smoke_m9_harmonia.py --pasta $Harmonia
        $smokeExit = $LASTEXITCODE
        if ($smokeExit -ne 0) {
            Write-Host "AVISO: smoke M9 retornou exit $smokeExit (diff ou checks) - ver output/m9_smoke_relatorio.json" -ForegroundColor Yellow
        }
    } else {
        Write-Host "AVISO: pasta Harmonia nao encontrada - smoke pulado" -ForegroundColor Yellow
    }
}

Invoke-Step "pytest nucleo (anel 1 + validacao saida)" {
    Push-Location (Join-Path $Repo "Fase_1_Desktop\nucleo")
    & $VenvPy -m pytest -q
    Pop-Location
}

@{
    quando = (Get-Date).ToUniversalTime().ToString("o")
    repo = $Repo
    harmonia = $Harmonia
    smoke_exit = $smokeExit
    passos = @("smoke_m9", "pytest")
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $RelJson -Encoding UTF8

Write-Host ""
Write-Host "M9 fechamento concluido. Relatorio: $RelJson" -ForegroundColor Green
Write-Host "Nota: diff <0,3% pode falhar ate ajuste cartografico - ver docs/m9-conformidade-harmonia.md" -ForegroundColor DarkGray

if (-not $SemCommit) {
    Write-Host "Faca git add/commit/push apos revisar o diff." -ForegroundColor DarkGray
}
