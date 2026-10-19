"""ocr.py — 把 JD 截图转成纯文本（Windows 内置 OCR，离线、无第三方依赖）。

设计原则（隐私 + 省 token）：
  - 全程本地，不联网；
  - 只把识别出的**文本**交给后续流程，**绝不把图片本身喂进上下文**（图片会随每轮重发，极耗 token）。

截图 → `jd2word ocr --img 截图.png --out jd.txt` → 只读 jd.txt。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_PS_SCRIPT = r"""
param(
  [Parameter(Mandatory = $true)][string]$Img,
  [Parameter(Mandatory = $true)][string]$Out
)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]

function Await($WinRtTask, $ResultType) {
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
  })[0]
  $netTask = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}

try {
  $file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Img)) ([Windows.Storage.StorageFile])
  $stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $engine  = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  if ($null -eq $engine) { Write-Output "NO_ENGINE"; exit 1 }
  $result  = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $text = ($result.Lines | ForEach-Object { $_.Text }) -join "`r`n"
  [System.IO.File]::WriteAllText($Out, $text, [System.Text.Encoding]::UTF8)
  Write-Output ("OK lines=" + @($result.Lines).Count + " -> " + $Out)
} catch {
  Write-Output ("ERROR: " + $_.Exception.Message)
  exit 1
}
"""


def ocr_image(img: str | Path, out: str | Path) -> str:
    """识别图片文字，写入 out（UTF-8），返回识别文本。仅支持 Windows。"""
    if sys.platform != "win32":
        raise RuntimeError(
            "内置 OCR 依赖 Windows 系统自带识别引擎，当前系统不是 Windows。\n"
            "非 Windows 用户可：① 安装任意 OCR 工具先把截图转成文本，再把文本交给流程；\n"
            "② 或把 JD 直接以文字形式提供。"
        )
    img, out = Path(img), Path(out)
    if not img.exists():
        raise FileNotFoundError(f"截图不存在：{img}")
    out.parent.mkdir(parents=True, exist_ok=True)

    ps1 = Path(tempfile.gettempdir()) / "jd2word_ocr.ps1"
    ps1.write_text(_PS_SCRIPT, encoding="utf-8-sig")

    exe = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"
    proc = subprocess.run(
        [exe, "-NoProfile", "-File", str(ps1), "-Img", str(img), "-Out", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    line = (proc.stdout or "").strip().splitlines()
    head = line[-1] if line else ""
    if proc.returncode != 0 or head.startswith("ERROR") or head == "NO_ENGINE":
        raise RuntimeError(f"OCR 失败：{head or proc.stderr.strip()}")
    return out.read_text(encoding="utf-8")
