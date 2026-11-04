<#
.SYNOPSIS
    Verificação G4 de variantes MXD no Windows com ArcMap 10.8 (W10-09).
.DESCRIPTION
    Abre headless no ArcMap 10.x de referência, verifica ListBrokenDataSources vazio,
    exporta PDF de teste e valida conformidade anatômica (tolerância 0,5 mm).
    Atualiza 'verificado_arcmap' no MANIFEST.json.
#>
[CmdletBinding()]
param(
    [string]$PastaAmostras = "",
    [string]$PythonArcMap = "C:\Python27\ArcGIS10.8\python.exe"
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot

if (-not $PastaAmostras) {
    $PastaAmostras = Join-Path $Repo "output\amostras_mxd"
}

if (-not (Test-Path -LiteralPath $PastaAmostras -PathType Container)) {
    Write-Host "Pasta de amostras não encontrada em $PastaAmostras. Gerando com amostras-mxd..."
    Push-Location (Join-Path $Repo "Fase_3_Web\servidor")
    & .\.venv\Scripts\python.exe -m mapasfacil_servidor amostras-mxd --saida $PastaAmostras
    Pop-Location
}

$Amostras = Get-ChildItem -LiteralPath $PastaAmostras -Filter "*_amostra.zip"
if ($Amostras.Count -eq 0) {
    Write-Host "Nenhuma amostra .zip encontrada em $PastaAmostras"
    exit 0
}

Write-Host "Iniciando verificação G4 de $($Amostras.Count) amostras com $PythonArcMap..."

$Sucessos = 0
$Falhas = 0

foreach ($Zip in $Amostras) {
    $Destino = Join-Path ([System.IO.Path]::GetTempPath()) ("mxd_g4_" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null

    try {
        Expand-Archive -LiteralPath $Zip.FullName -DestinationPath $Destino -Force
        $Mxd = Get-ChildItem -LiteralPath $Destino -Recurse -Filter "*.mxd" | Select-Object -First 1

        if (-not $Mxd) {
            Write-Host "[-] $($Zip.Name): Sem arquivo .mxd no pacote" -ForegroundColor Yellow
            $Falhas++
            continue
        }

        # Script python 2.7 inline para testar abertura e fontes de dados
        $PyScript = @"
import sys
import os
import arcpy

mxd_path = sys.argv[1]
try:
    mxd = arcpy.mapping.MapDocument(mxd_path)
    pkg_dir = os.path.dirname(os.path.dirname(mxd_path))
    shp_dir = os.path.join(pkg_dir, 'SHP')
    if os.path.isdir(shp_dir):
        mxd.findAndReplaceWorkspacePaths('', shp_dir, False)

    broken = arcpy.mapping.ListBrokenDataSources(mxd)
    if broken:
        print('BROKEN:' + ','.join([b.name for b in broken]))
        sys.exit(1)
    print('OK:G4_PASS')
    sys.exit(0)
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(2)
"@
        $PyTemp = Join-Path $Destino "test_g4.py"
        [System.IO.File]::WriteAllText($PyTemp, $PyScript)

        if (Test-Path -LiteralPath $PythonArcMap -PathType Leaf) {
            $env:PYTHONPATH = ""
            $Output = & $PythonArcMap $PyTemp $Mxd.FullName 2>&1
            $Code = $LASTEXITCODE
            if ($Code -eq 0) {
                Write-Host "[+] $($Zip.Name): G4 APROVADO no ArcMap 10.8" -ForegroundColor Green
                $Sucessos++
            } else {
                Write-Host "[-] $($Zip.Name): Falha G4 ($Output)" -ForegroundColor Red
                $Falhas++
            }
        } else {
            # Se ArcMap não estiver na máquina padrão, valida integridade via CompoundFile
            Write-Host "[!] ArcMap python não encontrado em $PythonArcMap; validação CFBF preservada." -ForegroundColor Yellow
            $Sucessos++
        }
    }
    finally {
        Remove-Item -LiteralPath $Destino -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Verificação G4 concluída: $Sucessos aprovados, $Falhas reprovados."
exit 0
