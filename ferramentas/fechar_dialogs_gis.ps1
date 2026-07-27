# Fecha automaticamente o dialogo "GIS Server Connection" do ArcMap.
# Uso: powershell -ExecutionPolicy Bypass -File ferramentas/fechar_dialogs_gis.ps1

$ErrorActionPreference = 'SilentlyContinue'
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class GisDlgKiller {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] static extern IntPtr GetDlgItem(IntPtr hDlg, int nIDDlgItem);
  [DllImport("user32.dll")] static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

  const uint WM_CLOSE = 0x0010;
  const uint BM_CLICK = 0x00F5;
  const int IDCANCEL = 2;
  const byte VK_ESCAPE = 0x1B;
  const uint KEYEVENTF_KEYUP = 0x0002;

  static List<IntPtr> hits;

  static bool Collect(IntPtr hWnd, IntPtr lParam) {
    if (!IsWindowVisible(hWnd)) return true;
    var sb = new StringBuilder(512);
    GetWindowText(hWnd, sb, 512);
    string t = sb.ToString();
    if (t.IndexOf("GIS Server Connection", StringComparison.OrdinalIgnoreCase) >= 0 ||
        t.IndexOf("Authentication Required", StringComparison.OrdinalIgnoreCase) >= 0 ||
        t.IndexOf("Enter Credentials", StringComparison.OrdinalIgnoreCase) >= 0) {
      hits.Add(hWnd);
    }
    return true;
  }

  public static int CloseAll() {
    hits = new List<IntPtr>();
    EnumWindows(Collect, IntPtr.Zero);
    int n = 0;
    foreach (var h in hits) {
      IntPtr btn = GetDlgItem(h, IDCANCEL);
      if (btn != IntPtr.Zero) PostMessage(btn, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
      PostMessage(h, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
      keybd_event(VK_ESCAPE, 0, 0, UIntPtr.Zero);
      keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
      n++;
    }
    return n;
  }
}
"@

$fechados = 0
Write-Host "Monitor GIS Server Connection - Ctrl+C para parar"
while ($true) {
  $n = [GisDlgKiller]::CloseAll()
  if ($n -gt 0) {
    $fechados += $n
    Write-Host ("[{0}] fechou {1} dialogo(s) - total {2}" -f (Get-Date -Format 'HH:mm:ss'), $n, $fechados)
    Start-Sleep -Milliseconds 150
  } else {
    Start-Sleep -Milliseconds 200
  }
}
