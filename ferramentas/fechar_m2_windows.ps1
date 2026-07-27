# Fecha M2 no Windows: template ArcMap + B2 + smoke Harmonia + testes.
# Uso (ArcMap FECHADO):
#   powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m2_windows.ps1
#   powershell -ExecutionPolicy Bypass -File ferramentas\fechar_m2_windows.ps1 -Harmonia "C:\...\Harmonia"

param(
    [string]$Harmonia = "",
    [switch]$SemSmoke,
    [switch]$SemCommit
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$ArcPy = "C:\Python27\ArcGIS10.8\python.exe"
if (-not (Test-Path -LiteralPath $ArcPy)) {
    throw "Python do ArcMap nao encontrado: $ArcPy"
}

$VenvPy = Join-Path $Repo "Fase_1_Desktop\nucleo\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPy)) {
    throw "venv do nucleo ausente. Rode: cd Fase_1_Desktop\nucleo; py -3.12 -m venv .venv; pip install -e .[dev]"
}

$Mxd = Join-Path $Repo "shared\templates\Dinamica_retrato.mxd"
$OutDir = Join-Path $Repo "output"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$RelJson = Join-Path $OutDir "m2_fechamento_relatorio.json"

function Invoke-Step([string]$Titulo, [scriptblock]$Block) {
    Write-Host ""
    Write-Host "== $Titulo ==" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        throw "Falhou: $Titulo (exit $LASTEXITCODE)"
    }
}

Invoke-Step "Inspecao pre" {
    & $ArcPy ferramentas\inspecionar_mxd_arcpy.py $Mxd -o (Join-Path $OutDir "inspecao_template_pre.json")
}

Invoke-Step "Corrigir template (fechar_m2_template_arcpy)" {
    $argsList = @("ferramentas\fechar_m2_template_arcpy.py", "--mxd", $Mxd, "-o", (Join-Path $OutDir "fechar_template.json"))
    if ($Harmonia) { $argsList += @("--harmonia", $Harmonia) }
    & $ArcPy @argsList
}

Invoke-Step "Preparar sentinelas B2" {
    & $ArcPy ferramentas\preparar_sentinelas_arcpy.py $Mxd
}

Invoke-Step "Registrar template no MANIFEST" {
    & $VenvPy ferramentas\registrar_template.py dinamica_retrato $Mxd
}

Invoke-Step "Limpar chaves MXD" {
    & $VenvPy ferramentas\chaves_mxd.py limpar
    & $VenvPy ferramentas\chaves_mxd.py verificar
}

Invoke-Step "Inspecao pos" {
    & $ArcPy ferramentas\inspecionar_mxd_arcpy.py $Mxd -o (Join-Path $OutDir "inspecao_template_pos.json")
}

if (-not $SemSmoke) {
    if (-not $Harmonia) {
        $candidatos = Get-ChildItem -Path (Join-Path $env:USERPROFILE "Downloads\Analise_de_area") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "Harmonia" } |
            Select-Object -First 1
        if ($candidatos) { $Harmonia = $candidatos.FullName }
    }
    if ($Harmonia -and (Test-Path -LiteralPath $Harmonia)) {
        Invoke-Step "Smoke M2 Harmonia (T1)" {
            & $VenvPy ferramentas\smoke_m2_harmonia.py --pasta $Harmonia
        }
        Invoke-Step "Smoke M2 Harmonia (T2)" {
            & $VenvPy ferramentas\smoke_m2_harmonia.py --pasta $Harmonia --forcar-t2 --nome-base Dinamica_2026_MapasFacil_M2_T2
        }
    } else {
        Write-Host "AVISO: pasta Harmonia nao encontrada - smoke pulado" -ForegroundColor Yellow
    }
}

Invoke-Step "pytest nucleo (anel 1)" {
    Push-Location (Join-Path $Repo "Fase_1_Desktop\nucleo")
    & $VenvPy -m pytest -q
    Pop-Location
}

@{
    quando = (Get-Date).ToUniversalTime().ToString("o")
    repo = $Repo
    harmonia = $Harmonia
    mxd = $Mxd
    passos = @("inspecao_pre", "fechar_template", "sentinelas", "manifest", "chaves", "inspecao_pos", "smoke", "pytest")
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $RelJson -Encoding UTF8

Write-Host ""
Write-Host "M2 fechamento OK. Relatorio: $RelJson" -ForegroundColor Green

if (-not $SemCommit) {
    Write-Host "Faca git add/commit/push apos revisar o diff." -ForegroundColor DarkGray
}
