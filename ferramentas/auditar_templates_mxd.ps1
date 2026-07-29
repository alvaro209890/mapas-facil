[CmdletBinding()]
param(
    [string]$Templates = "",
    [string]$Saida = "",
    [string]$PythonArcMap = "C:\Python27\ArcGIS10.8\python.exe",
    [switch]$IncluirDinamicaRetrato
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if (-not $Templates) {
    $Templates = Join-Path $Repo "shared\templates"
}
if (-not $Saida) {
    $Saida = Join-Path $Repo "output\mxd_auditoria_templates"
}

if (-not (Test-Path -LiteralPath $PythonArcMap -PathType Leaf)) {
    throw "Python do ArcMap não encontrado: $PythonArcMap"
}
if (-not (Test-Path -LiteralPath $Templates -PathType Container)) {
    throw "Pasta de templates não encontrada: $Templates"
}

New-Item -ItemType Directory -Force -Path $Saida | Out-Null
$Inspector = Join-Path $PSScriptRoot "inspecionar_mxd_arcpy.py"
$Arquivos = Get-ChildItem -LiteralPath $Templates -Filter "*.mxd" |
    Where-Object { $IncluirDinamicaRetrato -or $_.Name -ne "Dinamica_retrato.mxd" } |
    Sort-Object Name

$Resumo = @()
foreach ($Arquivo in $Arquivos) {
    $Relatorio = Join-Path $Saida ($Arquivo.BaseName + ".json")
    & $PythonArcMap $Inspector $Arquivo.FullName -o $Relatorio
    $Codigo = $LASTEXITCODE
    if ($Codigo -ne 0 -or -not (Test-Path -LiteralPath $Relatorio -PathType Leaf)) {
        $Resumo += [pscustomobject]@{
            arquivo = $Arquivo.Name
            pronto_b1 = $false
            quebradas = $null
            crs_mapa = $null
            faltas = @("falha_inspecao")
            codigo = $Codigo
        }
        continue
    }

    $Dados = Get-Content -LiteralPath $Relatorio -Raw -Encoding UTF8 | ConvertFrom-Json
    $Mapa = $Dados.data_frames | Where-Object { $_.name -eq "MAPA" } | Select-Object -First 1
    $Faltas = @(
        $Dados.diagnostico.faltam_data_frames
        $Dados.diagnostico.faltam_text_elements
        $Dados.diagnostico.faltam_graphics
        $Dados.diagnostico.faltam_pictures
        $Dados.diagnostico.faltam_legends
        $Dados.diagnostico.faltam_mapsurrounds
    ) | Where-Object { $_ }
    $Resumo += [pscustomobject]@{
        arquivo = $Arquivo.Name
        pronto_b1 = [bool]$Dados.diagnostico.pronto_b1
        quebradas = [int]$Dados.diagnostico.quebradas
        crs_mapa = $Mapa.sr
        faltas = @($Faltas)
        codigo = $Codigo
    }
}

$ResumoPath = Join-Path $Saida "resumo.json"
$Resumo | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResumoPath -Encoding UTF8
$Pendentes = @($Resumo | Where-Object { -not $_.pronto_b1 })

$Resumo | Format-Table arquivo, pronto_b1, quebradas, crs_mapa, codigo -AutoSize
Write-Output "Relatório: $ResumoPath"
Write-Output "TOTAL=$($Resumo.Count) PRONTOS=$($Resumo.Count - $Pendentes.Count) PENDENTES=$($Pendentes.Count)"
if ($Pendentes.Count -gt 0) {
    exit 2
}
