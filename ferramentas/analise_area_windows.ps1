[CmdletBinding()]
param(
    [string]$Repo = "",
    [string]$Dados = "",
    [string]$Modelo = "",
    [ValidateRange(1, 5)][int]$Tentativas = 5,
    [switch]$SemCommit,
    [switch]$SemArcpy
)

$ErrorActionPreference = "Stop"
if (-not $Repo) {
    $Repo = Split-Path -Parent $PSScriptRoot
}
$Repo = [System.IO.Path]::GetFullPath($Repo)
if (-not $Dados) {
    $Dados = Join-Path $Repo "Testes\01_analise_04_Julio\ATP_Teste"
}
if (-not $Modelo) {
    $Modelo = Join-Path $Repo "Testes\01_analise_04_Julio\Modelo"
}
$Dados = [System.IO.Path]::GetFullPath($Dados)
$Modelo = [System.IO.Path]::GetFullPath($Modelo)
$Output = Join-Path $Repo "output"
$Nucleo = Join-Path $Repo "Fase_1_Desktop\nucleo"
$App = Join-Path $Repo "Fase_1_Desktop\app"
$Python = Join-Path $Nucleo ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $Output | Out-Null

$Passos = [ordered]@{}
function Invoke-Passo {
    param(
        [Parameter(Mandatory = $true)][string]$Nome,
        [Parameter(Mandatory = $true)][scriptblock]$Acao
    )
    $Inicio = Get-Date
    try {
        & $Acao
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "exit $LASTEXITCODE"
        }
        $Passos[$Nome] = [ordered]@{
            ok = $true
            segundos = [math]::Round(((Get-Date) - $Inicio).TotalSeconds, 1)
        }
    }
    catch {
        $Passos[$Nome] = [ordered]@{
            ok = $false
            segundos = [math]::Round(((Get-Date) - $Inicio).TotalSeconds, 1)
            erro = $_.Exception.Message
        }
        throw
    }
}

if (-not (Test-Path -LiteralPath $Dados -PathType Container)) {
    throw "Pasta de dados não encontrada: $Dados"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Venv do núcleo ausente: $Python"
}

Get-Process -Name ArcMap -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $Dados -Recurse -Filter "*.lock" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

try {
    if (-not $SemArcpy) {
        Invoke-Passo "W2_ambiente" {
            & powershell -NoProfile -ExecutionPolicy Bypass -File `
                (Join-Path $PSScriptRoot "detectar_arcmap.ps1") -Repo $Repo
        }
        Invoke-Passo "W3_auditoria_b1" {
            & powershell -NoProfile -ExecutionPolicy Bypass -File `
                (Join-Path $PSScriptRoot "auditar_templates_mxd.ps1") `
                -Templates (Join-Path $Repo "shared\templates") `
                -Saida (Join-Path $Output "mxd_auditoria_orquestrador")
        }
        Invoke-Passo "W4_offsets_manifesto" {
            & powershell -NoProfile -ExecutionPolicy Bypass -File `
                (Join-Path $PSScriptRoot "preparar_templates_serie_mxd.ps1") `
                -Repo $Repo `
                -Auditoria (Join-Path $Output "mxd_auditoria_orquestrador")
        }
        Invoke-Passo "W5_serie_mxd" {
            $ArgsSmoke = @(
                (Join-Path $PSScriptRoot "smoke_serie_mxd.py"),
                "--workspace", $Dados,
                "--saida-relatorio", (Join-Path $Output "w5_serie_mxd.json")
            )
            $PastaAnalise = Join-Path $Dados "SHP\analise"
            if (-not (Test-Path -LiteralPath $PastaAnalise -PathType Container)) {
                $ArgsSmoke += "--preparar-camadas"
            }
            $PastaModelos = Join-Path $Modelo "Mapas"
            if (Test-Path -LiteralPath $PastaModelos -PathType Container) {
                $ArgsSmoke += @("--modelos", $PastaModelos)
            }
            $Concluiu = $false
            for ($Tentativa = 1; $Tentativa -le $Tentativas; $Tentativa++) {
                & $Python @ArgsSmoke
                if ($LASTEXITCODE -eq 0) {
                    $Concluiu = $true
                    break
                }
                Write-Warning "W5 falhou na tentativa $Tentativa de $Tentativas."
            }
            if (-not $Concluiu) {
                throw "W5 não ficou verde após $Tentativas tentativa(s)."
            }
        }
    }

    Invoke-Passo "W8_pytest" {
        Push-Location $Nucleo
        try { & $Python -m pytest -q } finally { Pop-Location }
    }
    Invoke-Passo "W8_app" {
        Push-Location $App
        try {
            & pnpm typecheck
            if ($LASTEXITCODE -ne 0) { throw "pnpm typecheck falhou" }
            & pnpm test
            if ($LASTEXITCODE -ne 0) { throw "pnpm test falhou" }
            & pnpm build
        }
        finally { Pop-Location }
    }
    Invoke-Passo "W8_goal" {
        & $Python (Join-Path $PSScriptRoot "validar_goal_analise.py")
    }
    Invoke-Passo "W8_segredos" {
        & $Python (Join-Path $PSScriptRoot "chaves_mxd.py") verificar
    }

    if (-not $SemCommit) {
        Invoke-Passo "W8_git" {
            Push-Location $Repo
            try {
                & git add --all
                & git commit -m "feat: concluir geração MXD da análise de área"
                & git push origin main
            }
            finally { Pop-Location }
        }
    }
}
finally {
    $Relatorio = [ordered]@{
        ok = -not @($Passos.Values | Where-Object { -not $_.ok }).Count
        repo = $Repo
        dados = $Dados
        modelo = $Modelo
        tentativas_maximas = $Tentativas
        sem_arcpy = [bool]$SemArcpy
        sem_commit = [bool]$SemCommit
        passos = $Passos
    }
    $Relatorio | ConvertTo-Json -Depth 7 |
        Set-Content -LiteralPath (Join-Path $Output "analise_area_windows_relatorio.json") -Encoding UTF8
}

Write-Output "Fase W concluída."
