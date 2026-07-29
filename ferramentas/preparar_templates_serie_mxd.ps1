[CmdletBinding()]
param(
    [string]$Repo = "",
    [string]$Auditoria = "",
    [string]$PythonArcMap = "C:\Python27\ArcGIS10.8\python.exe",
    [int]$TimeoutSegundos = 150
)

$ErrorActionPreference = "Stop"
if (-not $Repo) {
    $Repo = Split-Path -Parent $PSScriptRoot
}
$Repo = [System.IO.Path]::GetFullPath($Repo)
if (-not $Auditoria) {
    $Auditoria = Join-Path $Repo "output\mxd_auditoria_pos_clone"
}
$Templates = Join-Path $Repo "shared\templates"
$Manifesto = Join-Path $Templates "MANIFEST.json"
$LogDir = Join-Path $Repo "output\mxd_preparacao_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Invoke-ArcPyComTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string[]]$Argumentos,
        [Parameter(Mandatory = $true)][string]$Rotulo
    )
    $Stdout = Join-Path $LogDir "$Rotulo.stdout.log"
    $Stderr = Join-Path $LogDir "$Rotulo.stderr.log"
    $Processo = Start-Process -FilePath $PythonArcMap `
        -ArgumentList (@($Script) + $Argumentos) `
        -WindowStyle Hidden `
        -RedirectStandardOutput $Stdout `
        -RedirectStandardError $Stderr `
        -PassThru
    if (-not $Processo.WaitForExit($TimeoutSegundos * 1000)) {
        Stop-Process -Id $Processo.Id -Force -ErrorAction SilentlyContinue
        throw "Timeout de $TimeoutSegundos s no ArcPy: $Rotulo"
    }
    # O overload com timeout não hidrata ExitCode/streams no Windows PowerShell
    # até uma segunda espera sem timeout.
    $Processo.WaitForExit()
    $Processo.Refresh()
    $Codigo = $Processo.ExitCode
    if ($null -eq $Codigo -or "$Codigo" -eq "") {
        # Windows PowerShell 5 pode perder ExitCode quando stdout/stderr são
        # redirecionados. O contrato de sucesso do preparador é explícito.
        $TextoSaida = Get-Content -LiteralPath $Stdout -Raw -ErrorAction SilentlyContinue
        $TextoErro = Get-Content -LiteralPath $Stderr -Raw -ErrorAction SilentlyContinue
        $Codigo = if ($TextoSaida -match "Sidecar:" -and -not $TextoErro) { 0 } else { 1 }
    }
    if ($Codigo -ne 0) {
        $Erro = Get-Content -LiteralPath $Stderr -Raw -ErrorAction SilentlyContinue
        throw "ArcPy falhou em $Rotulo (exit $Codigo): $Erro"
    }
}

Get-Process -Name ArcMap -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $Templates -Filter "*.lock" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

& python (Join-Path $PSScriptRoot "chaves_mxd.py") limpar
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao limpar segredos dos templates MXD."
}

$DadosManifesto = Get-Content -LiteralPath $Manifesto -Raw -Encoding UTF8 | ConvertFrom-Json
$Series = @($DadosManifesto.templates | Where-Object { $_.id -like "serie_*" })
if ($Series.Count -ne 20) {
    throw "Esperados 20 templates serie_*, encontrados $($Series.Count)."
}

$Resultados = @()
foreach ($Template in ($Series | Sort-Object { $_.serie.ordem })) {
    $Nome = Split-Path -Leaf $Template.fonte_acervo
    $Mxd = Join-Path $Templates $Nome
    $Relatorio = Join-Path $Auditoria (([System.IO.Path]::GetFileNameWithoutExtension($Nome)) + ".json")
    if (-not (Test-Path -LiteralPath $Mxd -PathType Leaf)) {
        throw "Template preparado ausente: $Mxd"
    }
    if (-not (Test-Path -LiteralPath $Relatorio -PathType Leaf)) {
        throw "Auditoria ausente: $Relatorio"
    }
    $Audit = Get-Content -LiteralPath $Relatorio -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Audit.diagnostico.pronto_b1) {
        throw "Template não passou B1: $Nome"
    }
    $Mapa = $Audit.data_frames | Where-Object { $_.name -eq "MAPA" } | Select-Object -First 1
    if (-not $Mapa.sr) {
        throw "CRS do MAPA não identificado: $Nome"
    }
    $Crs = "EPSG:$($Mapa.sr)"
    $Rotulo = "{0:D2}_{1}" -f [int]$Template.serie.ordem, $Template.id

    Invoke-ArcPyComTimeout `
        -Script (Join-Path $PSScriptRoot "preparar_sentinelas_arcpy.py") `
        -Argumentos @($Mxd) `
        -Rotulo $Rotulo

    & python (Join-Path $PSScriptRoot "registrar_template.py") `
        $Template.id $Mxd --crs-data-frame $Crs
    if ($LASTEXITCODE -ne 0) {
        throw "Registro no MANIFEST falhou: $($Template.id)"
    }
    $Resultados += [ordered]@{
        id = $Template.id
        arquivo = $Nome
        crs_data_frame = $Crs
        pronto_b1 = $true
        registrado = $true
    }
    Write-Output "[$($Template.serie.ordem)/20] $($Template.id) pronto"
}

# Os quatro cards individuais reutilizam os mesmos binários já calibrados.
$Adicionais = [ordered]@{
    "dinamica_quantitativos_retrato" = "Dinamica_2026_quantitativos.mxd"
    "tipologia_paisagem" = "Tipologia.mxd"
    "terras_indigenas_paisagem" = "Terras_Indigenas.mxd"
    "uc_paisagem" = "Unidade_de_Conservação.mxd"
}
foreach ($Par in $Adicionais.GetEnumerator()) {
    $Mxd = Join-Path $Templates $Par.Value
    $Relatorio = Join-Path $Auditoria (([System.IO.Path]::GetFileNameWithoutExtension($Par.Value)) + ".json")
    $Audit = Get-Content -LiteralPath $Relatorio -Raw -Encoding UTF8 | ConvertFrom-Json
    $Mapa = $Audit.data_frames | Where-Object { $_.name -eq "MAPA" } | Select-Object -First 1
    & python (Join-Path $PSScriptRoot "registrar_template.py") `
        $Par.Key $Mxd --crs-data-frame "EPSG:$($Mapa.sr)"
    if ($LASTEXITCODE -ne 0) {
        throw "Registro adicional no MANIFEST falhou: $($Par.Key)"
    }
}

& python (Join-Path $PSScriptRoot "chaves_mxd.py") verificar
if ($LASTEXITCODE -ne 0) {
    throw "Verificação de segredos falhou após preparar templates."
}

$Saida = Join-Path $Repo "output\w4_templates.json"
[ordered]@{
    ok = $true
    total = $Resultados.Count
    templates = $Resultados
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Saida -Encoding UTF8
Write-Output "Relatório: $Saida"
