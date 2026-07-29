[CmdletBinding()]
param(
    [string]$Repo = "",
    [string]$Saida = "",
    [string]$PythonArcMap = ""
)

$ErrorActionPreference = "Stop"
if (-not $Repo) {
    $Repo = Split-Path -Parent $PSScriptRoot
}
$Repo = [System.IO.Path]::GetFullPath($Repo)
if (-not $Saida) {
    $Saida = Join-Path $Repo "output\w0_ambiente.json"
}

$ArcMap = Get-ChildItem -Path @(
    "C:\Program Files (x86)\ArcGIS\Desktop10.*\bin\ArcMap.exe",
    "C:\Program Files\ArcGIS\Desktop10.*\bin\ArcMap.exe"
) -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $ArcMap) {
    throw "ArcMap Desktop 10.x não encontrado."
}

if (-not $PythonArcMap) {
    $VersaoPasta = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $ArcMap.FullName))
    $Versao = $VersaoPasta -replace "^Desktop", ""
    $PythonArcMap = "C:\Python27\ArcGIS$Versao\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonArcMap -PathType Leaf)) {
    $PythonArcMap = Get-ChildItem "C:\Python27\ArcGIS10.*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $PythonArcMap -or -not (Test-Path -LiteralPath $PythonArcMap -PathType Leaf)) {
    throw "Python 2.7 com ArcPy não encontrado."
}

$Codigo = @'
import arcpy, json, sys
info = arcpy.GetInstallInfo()
print(json.dumps({
    'arcpy_ok': True,
    'versao': info.get('Version'),
    'produto': arcpy.ProductInfo(),
    'licencas': {
        'ArcView': arcpy.CheckProduct('ArcView'),
        'ArcEditor': arcpy.CheckProduct('ArcEditor'),
        'ArcInfo': arcpy.CheckProduct('ArcInfo')
    },
    'python': sys.executable
}))
'@
$Bruto = & $PythonArcMap -c $Codigo
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao importar/consultar ArcPy (exit $LASTEXITCODE)."
}
$ArcPy = $Bruto | Select-Object -Last 1 | ConvertFrom-Json
$Licenciada = @($ArcPy.licencas.PSObject.Properties.Value) |
    Where-Object { $_ -ne "Unavailable" }
if (-not $Licenciada) {
    throw "ArcMap encontrado, mas nenhuma licença ArcView/ArcEditor/ArcInfo está disponível."
}

$Resultado = [ordered]@{
    ok = $true
    detectado_em = (Get-Date).ToString("o")
    arcmap = $ArcMap.FullName
    versao = $ArcPy.versao
    python_arcpy = $PythonArcMap
    produto = $ArcPy.produto
    licencas = $ArcPy.licencas
}
$PastaSaida = Split-Path -Parent $Saida
New-Item -ItemType Directory -Force -Path $PastaSaida | Out-Null
$Resultado | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Saida -Encoding UTF8
$Resultado | ConvertTo-Json -Depth 5
Write-Output "Relatório: $Saida"
