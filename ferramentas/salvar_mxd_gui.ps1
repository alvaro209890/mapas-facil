# Abre cada .mxd no ArcMap, fecha dialogos GIS Server Connection, salva (Ctrl+S) e fecha.
# Use em paralelo com fechar_dialogs_gis.ps1 (ou deixe -AutoClose ligado, padrao).
#
# Exemplo:
#   powershell -ExecutionPolicy Bypass -File ferramentas/salvar_mxd_gui.ps1
#   powershell -ExecutionPolicy Bypass -File ferramentas/salvar_mxd_gui.ps1 -Pastas @('Referencias_IMAP\MXD') -TimeoutSec 45

param(
  [string[]]$Pastas = @(
    'Referencias_IMAP\MXD',
    'Referencias_IMAP\Mapas\03\MXD',
    'Referencias_IMAP\Mapas\04\MXD',
    'Referencias_IMAP\Mapas\05\MXD',
    'Referencias_IMAP\Mapas\06\MXD',
    'shared\templates'
  ),
  [int]$TimeoutSec = 50,
  [int]$StableSec = 3,
  [string]$Relatorio = 'relatorio_salvar_mxd_gui.json',
  [switch]$AutoClose = $true,
  [switch]$SkipSemPlanetUrl
)

$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
Set-Location $Root

$arcmap = 'C:\Program Files (x86)\ArcGIS\Desktop10.8\bin\ArcMap.exe'
if (-not (Test-Path $arcmap)) {
  $arcmap = @(Get-ChildItem 'C:\Program Files*\ArcGIS\Desktop*\bin\ArcMap.exe' -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName)[0]
}
if (-not $arcmap -or -not (Test-Path $arcmap)) {
  Write-Error 'ArcMap.exe nao encontrado'
  exit 1
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class MxdGuiSave {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] static extern IntPtr GetDlgItem(IntPtr hDlg, int nIDDlgItem);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

  const uint WM_CLOSE = 0x0010;
  const uint BM_CLICK = 0x00F5;
  const int IDCANCEL = 2;

  static List<IntPtr> hits;
  static IntPtr arcHwnd;
  static uint targetPid;

  static bool IsAuthDialog(string t) {
    return t.IndexOf("GIS Server Connection", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Authentication Required", StringComparison.OrdinalIgnoreCase) >= 0
        || t.IndexOf("Enter Credentials", StringComparison.OrdinalIgnoreCase) >= 0;
  }

  static bool CollectDlg(IntPtr hWnd, IntPtr lParam) {
    if (!IsWindowVisible(hWnd)) return true;
    var sb = new StringBuilder(512);
    GetWindowText(hWnd, sb, 512);
    if (IsAuthDialog(sb.ToString())) hits.Add(hWnd);
    return true;
  }

  static bool FindArc(IntPtr hWnd, IntPtr lParam) {
    if (!IsWindowVisible(hWnd)) return true;
    uint pid; GetWindowThreadProcessId(hWnd, out pid);
    if (pid != targetPid) return true;
    var sb = new StringBuilder(512);
    GetWindowText(hWnd, sb, 512);
    string t = sb.ToString();
    if (t.Length == 0) return true;
    if (IsAuthDialog(t)) return true;
    if (t.IndexOf("ArcMap", StringComparison.OrdinalIgnoreCase) >= 0 ||
        t.EndsWith(".mxd", StringComparison.OrdinalIgnoreCase) ||
        t.IndexOf(" - ArcMap", StringComparison.OrdinalIgnoreCase) >= 0) {
      arcHwnd = hWnd;
    }
    return true;
  }

  public static int CloseDialogs() {
    hits = new List<IntPtr>();
    EnumWindows(CollectDlg, IntPtr.Zero);
    int n = 0;
    foreach (var h in hits) {
      IntPtr btn = GetDlgItem(h, IDCANCEL);
      if (btn != IntPtr.Zero) PostMessage(btn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
      PostMessage(h, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
      n++;
    }
    return n;
  }

  public static int CountDialogs() {
    hits = new List<IntPtr>();
    EnumWindows(CollectDlg, IntPtr.Zero);
    return hits.Count;
  }

  public static IntPtr FindArcMap(uint pid) {
    targetPid = pid;
    arcHwnd = IntPtr.Zero;
    EnumWindows(FindArc, IntPtr.Zero);
    return arcHwnd;
  }

  public static bool Focus(IntPtr h) {
    ShowWindow(h, 5);
    return SetForegroundWindow(h);
  }
}
"@

function Test-HasPlanetUrl([string]$path) {
  try {
    $b = [IO.File]::ReadAllBytes($path)
    $t = [Text.Encoding]::Unicode.GetString($b)
    return [bool]($t -match 'tiles\.planet|api\.planet\.com|plak_')
  } catch { return $true }
}

function Get-MxdList {
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($p in $Pastas) {
    $full = Join-Path $Root $p
    if (-not (Test-Path -LiteralPath $full)) { continue }
    Get-ChildItem -LiteralPath $full -Filter *.mxd -File | ForEach-Object {
      if ($_.Name -match '__mf_tmp__') { return }
      if ($SkipSemPlanetUrl -and -not (Test-HasPlanetUrl $_.FullName)) { return }
      $out.Add($_.FullName)
    }
  }
  return $out
}

function Stop-OurArcMap([int]$pidKeep, [int[]]$before) {
  Stop-Process -Id $pidKeep -Force -ErrorAction SilentlyContinue
  Get-Process ArcMap -ErrorAction SilentlyContinue |
    Where-Object { $before -notcontains $_.Id } |
    Stop-Process -Force -ErrorAction SilentlyContinue
}

$mxds = @(Get-MxdList)
Write-Host ("MXDs a salvar na GUI: {0}" -f $mxds.Count)
Write-Host ("ArcMap: {0}" -f $arcmap)
Write-Host ("AutoClose={0} TimeoutSec={1}" -f $AutoClose, $TimeoutSec)

$resultados = @()
$i = 0
foreach ($mxd in $mxds) {
  $i++
  $name = Split-Path $mxd -Leaf
  Write-Host ("[{0}/{1}] {2}" -f $i, $mxds.Count, $name)
  $rec = [ordered]@{
    arquivo = $mxd
    ok = $false
    dialogos = 0
    salvou = $false
    ms = 0
    aviso = ''
  }
  $t0 = Get-Date
  $before = @(Get-Process ArcMap -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
  $sizeBefore = (Get-Item -LiteralPath $mxd).Length
  $mtimeBefore = (Get-Item -LiteralPath $mxd).LastWriteTimeUtc

  try {
    $proc = Start-Process -FilePath $arcmap -ArgumentList ("`"{0}`"" -f $mxd) -PassThru
    $stable = 0
    $ready = $false
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
      if ($AutoClose) {
        $n = [MxdGuiSave]::CloseDialogs()
        if ($n -gt 0) { $rec.dialogos += $n }
      } else {
        $n = [MxdGuiSave]::CountDialogs()
        if ($n -gt 0) { $rec.dialogos += $n }
      }
      $h = [MxdGuiSave]::FindArcMap([uint32]$proc.Id)
      if ($h -ne [IntPtr]::Zero -and [MxdGuiSave]::CountDialogs() -eq 0) {
        $stable++
        if ($stable -ge [Math]::Max(1, [int]($StableSec / 0.4))) {
          $ready = $true
          break
        }
      } else {
        $stable = 0
      }
      Start-Sleep -Milliseconds 400
    }

    if (-not $ready) {
      $rec.aviso = 'timeout aguardando ArcMap estavel sem dialogo'
    }

    $h = [MxdGuiSave]::FindArcMap([uint32]$proc.Id)
    if ($h -ne [IntPtr]::Zero) {
      [MxdGuiSave]::Focus($h) | Out-Null
      Start-Sleep -Milliseconds 600
      [System.Windows.Forms.SendKeys]::SendWait('{ESC}{ESC}^s')
      Start-Sleep -Seconds 4
      # segunda tentativa de save
      [MxdGuiSave]::Focus($h) | Out-Null
      [System.Windows.Forms.SendKeys]::SendWait('^s')
      Start-Sleep -Seconds 2
    }

    $item = Get-Item -LiteralPath $mxd
    if ($item.LastWriteTimeUtc -gt $mtimeBefore -or $item.Length -ne $sizeBefore) {
      $rec.salvou = $true
      $rec.ok = $true
    } elseif ($ready) {
      $rec.aviso = 'ArcMap abriu mas mtime/tamanho nao mudou (save duvidoso)'
      $rec.ok = $false
    }
  } catch {
    $rec.aviso = $_.Exception.Message
    $rec.ok = $false
  } finally {
    if ($proc) { Stop-OurArcMap -pidKeep $proc.Id -before $before }
    else { Stop-OurArcMap -pidKeep 0 -before $before }
    Start-Sleep -Seconds 1
    $rec.ms = [int]((Get-Date) - $t0).TotalMilliseconds
  }

  Write-Host ("  ok={0} dialogos={1} salvou={2} ms={3} {4}" -f $rec.ok, $rec.dialogos, $rec.salvou, $rec.ms, $rec.aviso)
  $resultados += $rec
}

$resumo = [ordered]@{
  gerado_em = (Get-Date).ToString('o')
  total = $resultados.Count
  ok = @($resultados | Where-Object { $_.ok }).Count
  com_dialogo = @($resultados | Where-Object { $_.dialogos -gt 0 }).Count
  falhas = @($resultados | Where-Object { -not $_.ok }).Count
  resultados = $resultados
}
$json = $resumo | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $Root $Relatorio), $json, [Text.UTF8Encoding]::new($false))
Write-Host ("Relatorio: {0}" -f $Relatorio)
Write-Host ("resumo: ok={0}/{1} com_dialogo={2} falhas={3}" -f $resumo.ok, $resumo.total, $resumo.com_dialogo, $resumo.falhas)
if ($resumo.falhas -gt 0) { exit 2 } else { exit 0 }
