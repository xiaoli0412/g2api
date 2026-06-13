param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidateSet("x64")]
    [string]$Platform = "x64",
    [string]$ExePath,
    [string]$OutputDirectory,
    [int]$TimeoutSeconds = 25,
    [int]$WarmupMilliseconds = 900,
    [switch]$Build,
    [switch]$KeepRunning,
    [switch]$ExerciseLanguageToggle,
    [switch]$ExerciseBackendControls
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ExePath) {
    $ExePath = Join-Path $repo "build\native\$Platform\$Configuration\Gemini2API.WinUI.exe"
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repo "output\native-visual"
}

if ($Build) {
    & (Join-Path $PSScriptRoot "build-winui.ps1") -Configuration $Configuration -Platform $Platform
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Missing WinUI executable: $ExePath. Run native\scripts\build-winui.ps1 first."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

if (-not ("Win32WindowProbe" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class Win32WindowProbe
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);

    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();

    [DllImport("user32.dll")]
    public static extern uint GetDpiForWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetWindowDpiAwarenessContext(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern int GetAwarenessFromDpiAwarenessContext(IntPtr value);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@
}

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
[void][Win32WindowProbe]::SetProcessDPIAware()

function Get-WindowTitle {
    param([IntPtr]$Handle)

    $length = [Win32WindowProbe]::GetWindowTextLength($Handle)
    if ($length -le 0) {
        return ""
    }

    $builder = New-Object System.Text.StringBuilder ($length + 1)
    [void][Win32WindowProbe]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-WindowRectangle {
    param([IntPtr]$Handle)

    $rect = New-Object "Win32WindowProbe+RECT"
    if (-not [Win32WindowProbe]::GetWindowRect($Handle, [ref]$rect)) {
        throw "Could not read window rectangle for handle $Handle."
    }

    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    return [pscustomobject]@{
        Left = $rect.Left
        Top = $rect.Top
        Right = $rect.Right
        Bottom = $rect.Bottom
        Width = $width
        Height = $height
    }
}

function Find-ProcessWindow {
    param([int]$ProcessId)

    $handles = New-Object "System.Collections.Generic.List[System.IntPtr]"
    $callback = {
        param([IntPtr]$hWnd, [IntPtr]$lParam)

        [uint32]$windowProcessId = 0
        [void][Win32WindowProbe]::GetWindowThreadProcessId($hWnd, [ref]$windowProcessId)
        if ([int]$windowProcessId -eq $ProcessId -and [Win32WindowProbe]::IsWindowVisible($hWnd)) {
            try {
                $rect = Get-WindowRectangle $hWnd
                if ($rect.Width -ge 360 -and $rect.Height -ge 240) {
                    [void]$handles.Add($hWnd)
                }
            } catch {
            }
        }

        return $true
    }.GetNewClosure()

    $enumProc = [Win32WindowProbe+EnumWindowsProc]$callback
    [void][Win32WindowProbe]::EnumWindows($enumProc, [IntPtr]::Zero)

    if ($handles.Count -eq 0) {
        return [IntPtr]::Zero
    }

    return $handles[0]
}

function Save-WindowScreenshot {
    param(
        [object]$Rect,
        [string]$Path,
        [IntPtr]$Handle = [IntPtr]::Zero
    )

    $bitmap = New-Object System.Drawing.Bitmap $Rect.Width, $Rect.Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        if ($Handle -ne [IntPtr]::Zero) {
            $hdc = $graphics.GetHdc()
            try {
                $printed = [Win32WindowProbe]::PrintWindow($Handle, $hdc, 0x00000002)
            } finally {
                $graphics.ReleaseHdc($hdc)
            }

            if ($printed) {
                $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
                return $bitmap
            }
        }

        $graphics.CopyFromScreen($Rect.Left, $Rect.Top, 0, 0, $bitmap.Size)
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        return $bitmap
    } catch {
        $bitmap.Dispose()
        throw
    } finally {
        $graphics.Dispose()
    }
}

function Invoke-LeftClick {
    param(
        [int]$X,
        [int]$Y
    )

    [void][Win32WindowProbe]::SetCursorPos($X, $Y)
    Start-Sleep -Milliseconds 80
    [Win32WindowProbe]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
    [Win32WindowProbe]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
}

function Find-AutomationElementById {
    param(
        [IntPtr]$Handle,
        [string]$AutomationId,
        [int]$TimeoutMilliseconds = 3500
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $rootElement = [System.Windows.Automation.AutomationElement]::FromHandle($Handle)
        if ($rootElement) {
            $condition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
                $AutomationId)
            $element = $rootElement.FindFirst(
                [System.Windows.Automation.TreeScope]::Descendants,
                $condition)
            if ($element) {
                return $element
            }
        }

        Start-Sleep -Milliseconds 100
    }

    return $null
}

function Get-AutomationNameById {
    param(
        [IntPtr]$Handle,
        [string]$AutomationId
    )

    $element = Find-AutomationElementById -Handle $Handle -AutomationId $AutomationId
    if (-not $element) {
        throw "UI Automation check failed: element '$AutomationId' was not found."
    }

    return $element.Current.Name
}

function Invoke-AutomationElementById {
    param(
        [IntPtr]$Handle,
        [string]$AutomationId
    )

    $element = Find-AutomationElementById -Handle $Handle -AutomationId $AutomationId
    if (-not $element) {
        throw "UI Automation check failed: element '$AutomationId' was not found."
    }

    $pattern = $element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    if (-not $pattern) {
        throw "UI Automation check failed: element '$AutomationId' does not expose InvokePattern."
    }

    $pattern.Invoke()
}

function Invoke-AutomationElementCenterById {
    param(
        [IntPtr]$Handle,
        [string]$AutomationId
    )

    $element = Find-AutomationElementById -Handle $Handle -AutomationId $AutomationId
    if (-not $element) {
        throw "UI Automation check failed: element '$AutomationId' was not found."
    }

    $bounds = $element.Current.BoundingRectangle
    if ($bounds.Width -le 0 -or $bounds.Height -le 0) {
        throw "UI Automation check failed: element '$AutomationId' has no clickable bounds."
    }

    Invoke-LeftClick `
        -X ([int]($bounds.Left + ($bounds.Width / 2))) `
        -Y ([int]($bounds.Top + ($bounds.Height / 2)))
}

function Test-LocalBackendReachable {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18081/" -UseBasicParsing -TimeoutSec 1
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-LocalBackendState {
    param(
        [bool]$Reachable,
        [int]$TimeoutMilliseconds = 12000
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ((Test-LocalBackendReachable) -eq $Reachable) {
            return
        }
        Start-Sleep -Milliseconds 300
    }

    if ($Reachable) {
        throw "Backend control check failed: local backend did not become reachable on 127.0.0.1:18081."
    }
    throw "Backend control check failed: local backend did not stop on 127.0.0.1:18081."
}

function Assert-AutomationElementExists {
    param(
        [IntPtr]$Handle,
        [string]$AutomationId
    )

    $element = Find-AutomationElementById -Handle $Handle -AutomationId $AutomationId
    if (-not $element) {
        throw "UI Automation check failed: required element '$AutomationId' was not found."
    }
}

function Measure-VisualSurface {
    param([System.Drawing.Bitmap]$Bitmap)

    $stride = [Math]::Max(1, [int][Math]::Floor([Math]::Min($Bitmap.Width, $Bitmap.Height) / 180))
    $total = 0
    $dark = 0
    $accent = 0
    $light = 0
    $buckets = @{}

    for ($y = 0; $y -lt $Bitmap.Height; $y += $stride) {
        for ($x = 0; $x -lt $Bitmap.Width; $x += $stride) {
            $pixel = $Bitmap.GetPixel($x, $y)
            $r = [int]$pixel.R
            $g = [int]$pixel.G
            $b = [int]$pixel.B
            $luma = (0.2126 * $r) + (0.7152 * $g) + (0.0722 * $b)

            if ($luma -ge 16 -and $luma -le 110 -and [Math]::Max([Math]::Max($r, $g), $b) -le 140) {
                $dark++
            }
            if ($r -le 48 -and $g -ge 80 -and $g -le 170 -and $b -ge 145 -and $b -le 245) {
                $accent++
            }
            if ($r -ge 205 -and $g -ge 205 -and $b -ge 205) {
                $light++
            }

            $bucket = "{0:X2}{1:X2}{2:X2}" -f ($r -band 0xF0), ($g -band 0xF0), ($b -band 0xF0)
            $buckets[$bucket] = $true
            $total++
        }
    }

    return [pscustomobject]@{
        Width = $Bitmap.Width
        Height = $Bitmap.Height
        Stride = $stride
        Samples = $total
        BucketCount = $buckets.Count
        DarkPixels = $dark
        DarkRatio = [Math]::Round($dark / [double]$total, 4)
        AccentPixels = $accent
        AccentRatio = [Math]::Round($accent / [double]$total, 4)
        LightPixels = $light
        LightRatio = [Math]::Round($light / [double]$total, 4)
    }
}

function Assert-VisualMetrics {
    param([object]$Metrics)

    if ($Metrics.BucketCount -lt 16) {
        throw "Visual check failed: screenshot looks blank or flat. Distinct color buckets: $($Metrics.BucketCount)."
    }
    if ($Metrics.DarkRatio -lt 0.30) {
        throw "Visual check failed: dark Windows surface ratio is too low ($($Metrics.DarkRatio))."
    }
    if ($Metrics.AccentPixels -lt 6) {
        throw "Visual check failed: Windows accent blue was not detected."
    }
    if ($Metrics.LightPixels -lt 10) {
        throw "Visual check failed: foreground text/icon pixels were not detected."
    }
}

function Convert-CodePointsToString {
    param([int[]]$Codes)

    return -join ($Codes | ForEach-Object { [char]$_ })
}

function Get-DpiAwarenessName {
    param([int]$Awareness)

    switch ($Awareness) {
        -1 { return "Invalid" }
        0 { return "Unaware" }
        1 { return "SystemAware" }
        2 { return "PerMonitorAware" }
        default { return "Unknown($Awareness)" }
    }
}

function Get-WindowDpiInfo {
    param([IntPtr]$Handle)

    $dpi = [Win32WindowProbe]::GetDpiForWindow($Handle)
    $context = [Win32WindowProbe]::GetWindowDpiAwarenessContext($Handle)
    $awareness = [Win32WindowProbe]::GetAwarenessFromDpiAwarenessContext($context)
    return [pscustomobject]@{
        Dpi = $dpi
        Scale = [Math]::Round($dpi / 96.0, 4)
        Awareness = $awareness
        AwarenessName = Get-DpiAwarenessName $awareness
    }
}

function Assert-DpiInfo {
    param([object]$DpiInfo)

    if ($DpiInfo.Dpi -lt 96) {
        throw "DPI check failed: target window reported invalid DPI $($DpiInfo.Dpi)."
    }
    if ($DpiInfo.Awareness -lt 2) {
        throw "DPI check failed: target window is $($DpiInfo.AwarenessName), expected PerMonitorAware/PerMonitorV2."
    }
}

function Get-RuntimeLogTail {
    $logPath = Join-Path $env:TEMP "Gemini2API.WinUI.runtime.log"
    if (-not (Test-Path -LiteralPath $logPath)) {
        return "Runtime log not found: $logPath"
    }

    try {
        return (Get-Content -LiteralPath $logPath -Encoding Unicode -Tail 80) -join [Environment]::NewLine
    } catch {
        return "Could not read runtime log: $($_.Exception.Message)"
    }
}

function Get-WinUiErrorEvents {
    try {
        $events = Get-WinEvent -LogName Application -MaxEvents 40 |
            Where-Object { $_.Message -match "Gemini2API|Microsoft\.UI\.Xaml|WindowsAppRuntime|combase" } |
            Select-Object -First 5 TimeCreated, ProviderName, Id, LevelDisplayName, Message

        if (-not $events) {
            return "No recent Gemini2API/WinUI Application log events were found."
        }

        return ($events | Format-List | Out-String).Trim()
    } catch {
        return "Could not read Application event log: $($_.Exception.Message)"
    }
}

function New-FailureMessage {
    param([string]$Message)

    return @"
$Message

--- Runtime log tail ---
$(Get-RuntimeLogTail)

--- Recent Application errors ---
$(Get-WinUiErrorEvents)
"@
}

$process = $null
$screenshotPath = $null
$metricsPath = $null

try {
    $process = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath) -PassThru -WindowStyle Normal
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $windowHandle = [IntPtr]::Zero
    $rect = $null

    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
        $process.Refresh()
        if ($process.HasExited) {
            throw (New-FailureMessage "WinUI process exited during startup with code $($process.ExitCode).")
        }

        $candidateHandle = [IntPtr]::Zero
        if ($process.MainWindowHandle -ne [IntPtr]::Zero) {
            $candidateHandle = $process.MainWindowHandle
        }

        if ($candidateHandle -ne [IntPtr]::Zero) {
            try {
                $candidateRect = Get-WindowRectangle $candidateHandle
                if ($candidateRect.Width -ge 360 -and $candidateRect.Height -ge 240) {
                    $windowHandle = $candidateHandle
                    $rect = $candidateRect
                    break
                }
            } catch {
                $candidateHandle = [IntPtr]::Zero
            }
        }

        $candidateHandle = Find-ProcessWindow -ProcessId $process.Id
        if ($candidateHandle -ne [IntPtr]::Zero) {
            try {
                $candidateRect = Get-WindowRectangle $candidateHandle
                if ($candidateRect.Width -ge 360 -and $candidateRect.Height -ge 240) {
                    $windowHandle = $candidateHandle
                    $rect = $candidateRect
                    break
                }
            } catch {
            }
        }
    }

    if ($windowHandle -eq [IntPtr]::Zero) {
        throw (New-FailureMessage "WinUI process started but no visible top-level window was found within $TimeoutSeconds seconds.")
    }

    if ([Win32WindowProbe]::IsIconic($windowHandle)) {
        [void][Win32WindowProbe]::ShowWindow($windowHandle, 9)
    } else {
        [void][Win32WindowProbe]::ShowWindow($windowHandle, 5)
    }
    [void][Win32WindowProbe]::SetWindowPos($windowHandle, [IntPtr]::new(-1), 0, 0, 0, 0, 0x0040 -bor 0x0002 -bor 0x0001)
    [void][Win32WindowProbe]::SetForegroundWindow($windowHandle)
    Start-Sleep -Milliseconds $WarmupMilliseconds

    $process.Refresh()
    if ($process.HasExited) {
        throw (New-FailureMessage "WinUI process exited after activation with code $($process.ExitCode).")
    }

    $freshHandle = Find-ProcessWindow -ProcessId $process.Id
    if ($freshHandle -ne [IntPtr]::Zero) {
        $windowHandle = $freshHandle
    }

    $rect = Get-WindowRectangle $windowHandle
    $dpiInfo = Get-WindowDpiInfo $windowHandle
    Assert-DpiInfo $dpiInfo
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "SegmentedModeBar"
    if ($rect.Width -lt 360 -or $rect.Height -lt 240) {
        throw (New-FailureMessage "WinUI window is too small for visual verification: $($rect.Width)x$($rect.Height).")
    }

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $screenshotPath = Join-Path $OutputDirectory "winui-runtime-$stamp.png"
    $metricsPath = Join-Path $OutputDirectory "winui-runtime-$stamp.json"
    $bitmap = Save-WindowScreenshot -Rect $rect -Path $screenshotPath -Handle $windowHandle

    try {
        $metrics = Measure-VisualSurface -Bitmap $bitmap
        Assert-VisualMetrics -Metrics $metrics
    } finally {
        $bitmap.Dispose()
    }

    $result = [ordered]@{
        executable = (Resolve-Path -LiteralPath $ExePath).Path
        processId = $process.Id
        windowHandle = ("0x{0:X}" -f $windowHandle.ToInt64())
        windowTitle = Get-WindowTitle $windowHandle
        screenshot = $screenshotPath
        window = [ordered]@{
            left = $rect.Left
            top = $rect.Top
            width = $rect.Width
            height = $rect.Height
        }
        metrics = $metrics
        dpi = [ordered]@{
            dpi = $dpiInfo.Dpi
            scale = $dpiInfo.Scale
            awareness = $dpiInfo.AwarenessName
        }
    }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metricsPath -Encoding UTF8

    Write-Host ("[OK] WinUI runtime launch verified: pid={0}, hwnd=0x{1:X}, size={2}x{3}" -f $process.Id, $windowHandle.ToInt64(), $rect.Width, $rect.Height)
    Write-Host ("[OK] DPI awareness verified: dpi={0}, scale={1}, awareness={2}" -f $dpiInfo.Dpi, $dpiInfo.Scale, $dpiInfo.AwarenessName)
    Write-Host "[OK] Native workbench UIA verified: SegmentedModeBar"
    Write-Host "[OK] Visual screenshot: $screenshotPath"
    Write-Host "[OK] Visual metrics: $metricsPath"

    Invoke-AutomationElementCenterById -Handle $windowHandle -AutomationId "NavServerButton"
    Start-Sleep -Milliseconds ([Math]::Max($WarmupMilliseconds, 700))
    $process.Refresh()
    if ($process.HasExited) {
        throw (New-FailureMessage "WinUI process exited after server navigation with code $($process.ExitCode).")
    }
    $freshHandle = Find-ProcessWindow -ProcessId $process.Id
    if ($freshHandle -ne [IntPtr]::Zero) {
        $windowHandle = $freshHandle
    }
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "StartBackendButton"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "StopBackendButton"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "OpenDashboardButton"
    Write-Host "[OK] Server process controls UIA verified: StartBackendButton, StopBackendButton, OpenDashboardButton"

    if ($ExerciseBackendControls) {
        if (Test-LocalBackendReachable) {
            throw "Backend control check refused to run because 127.0.0.1:18081 is already reachable."
        }

        Invoke-AutomationElementById -Handle $windowHandle -AutomationId "StartBackendButton"
        Wait-LocalBackendState -Reachable $true
        Assert-AutomationElementExists -Handle $windowHandle -AutomationId "StartBackendButton"

        Invoke-AutomationElementById -Handle $windowHandle -AutomationId "StopBackendButton"
        Wait-LocalBackendState -Reachable $false
        Write-Host "[OK] Server process controls exercised: backend started and stopped on 127.0.0.1:18081"
    }

    Invoke-AutomationElementCenterById -Handle $windowHandle -AutomationId "NavStreamingButton"
    Start-Sleep -Milliseconds ([Math]::Max($WarmupMilliseconds, 700))
    $process.Refresh()
    if ($process.HasExited) {
        throw (New-FailureMessage "WinUI process exited after workbench navigation with code $($process.ExitCode).")
    }
    $freshHandle = Find-ProcessWindow -ProcessId $process.Id
    if ($freshHandle -ne [IntPtr]::Zero) {
        $windowHandle = $freshHandle
    }
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "RecentRequestList"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "RequestBodyPreview"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "ResponseBodyPreview"
    Write-Host "[OK] Streaming workbench UIA verified: RecentRequestList, RequestBodyPreview, ResponseBodyPreview"

    Invoke-AutomationElementCenterById -Handle $windowHandle -AutomationId "NavModelsButton"
    Start-Sleep -Milliseconds ([Math]::Max($WarmupMilliseconds, 700))
    $process.Refresh()
    $freshHandle = Find-ProcessWindow -ProcessId $process.Id
    if ($freshHandle -ne [IntPtr]::Zero) {
        $windowHandle = $freshHandle
    }
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "NativeModelUsageTable"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "NativeModelUsageSummary"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "NativeQuotaTable"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "NativeQuotaSummary"
    Write-Host "[OK] Models workbench UIA verified: NativeModelUsageTable, NativeModelUsageSummary, NativeQuotaTable"

    if ($ExerciseLanguageToggle) {
        $beforeLanguageTitle = Get-AutomationNameById -Handle $windowHandle -AutomationId "PageTitle"
        Invoke-AutomationElementById -Handle $windowHandle -AutomationId "LanguageToggleButton"
        Start-Sleep -Milliseconds ([Math]::Max($WarmupMilliseconds, 800))

        $process.Refresh()
        if ($process.HasExited) {
            throw (New-FailureMessage "WinUI process exited after language-toggle interaction with code $($process.ExitCode).")
        }

        $freshHandle = Find-ProcessWindow -ProcessId $process.Id
        if ($freshHandle -ne [IntPtr]::Zero) {
            $windowHandle = $freshHandle
        }
        $rect = Get-WindowRectangle $windowHandle
        $afterLanguageTitle = Get-AutomationNameById -Handle $windowHandle -AutomationId "PageTitle"
        if ($beforeLanguageTitle -eq $afterLanguageTitle) {
            throw "Language toggle check failed: PageTitle did not change from '$beforeLanguageTitle'."
        }
        $overviewZh = Convert-CodePointsToString @(0x6982, 0x89C8)
        $serverZh = Convert-CodePointsToString @(0x670D, 0x52A1)
        $streamingZh = Convert-CodePointsToString @(0x5B9E, 0x65F6, 0x8BF7, 0x6C42)
        $modelsZh = Convert-CodePointsToString @(0x6A21, 0x578B)
        $logsZh = Convert-CodePointsToString @(0x65E5, 0x5FD7)
        $settingsZh = Convert-CodePointsToString @(0x8BBE, 0x7F6E)
        $expectedTitleAfterToggle = @{}
        $expectedTitleAfterToggle["Overview"] = $overviewZh
        $expectedTitleAfterToggle[$overviewZh] = "Overview"
        $expectedTitleAfterToggle["Server"] = $serverZh
        $expectedTitleAfterToggle[$serverZh] = "Server"
        $expectedTitleAfterToggle["Cookies"] = "Cookie"
        $expectedTitleAfterToggle["Cookie"] = "Cookies"
        $expectedTitleAfterToggle["Streaming"] = $streamingZh
        $expectedTitleAfterToggle[$streamingZh] = "Streaming"
        $expectedTitleAfterToggle["Models"] = $modelsZh
        $expectedTitleAfterToggle[$modelsZh] = "Models"
        $expectedTitleAfterToggle["Logs"] = $logsZh
        $expectedTitleAfterToggle[$logsZh] = "Logs"
        $expectedTitleAfterToggle["Settings"] = $settingsZh
        $expectedTitleAfterToggle[$settingsZh] = "Settings"
        if ($expectedTitleAfterToggle.ContainsKey($beforeLanguageTitle) -and
            $afterLanguageTitle -ne $expectedTitleAfterToggle[$beforeLanguageTitle]) {
            throw "Language toggle check failed: expected PageTitle '$($expectedTitleAfterToggle[$beforeLanguageTitle])' after toggle from '$beforeLanguageTitle', got '$afterLanguageTitle'."
        }

        $toggleScreenshotPath = Join-Path $OutputDirectory "winui-runtime-$stamp-language-toggle.png"
        $toggleBitmap = Save-WindowScreenshot -Rect $rect -Path $toggleScreenshotPath -Handle $windowHandle
        try {
            $toggleMetrics = Measure-VisualSurface -Bitmap $toggleBitmap
            Assert-VisualMetrics -Metrics $toggleMetrics
        } finally {
            $toggleBitmap.Dispose()
        }
        Write-Host ("[OK] WinUI language-toggle UIA verified: PageTitle '{0}' -> '{1}'" -f $beforeLanguageTitle, $afterLanguageTitle)
        Write-Host "[OK] WinUI language-toggle screenshot: $toggleScreenshotPath"
    }

    $resizeWidth = 900
    $resizeHeight = 620
    [void][Win32WindowProbe]::SetWindowPos($windowHandle, [IntPtr]::Zero, $rect.Left, $rect.Top, $resizeWidth, $resizeHeight, 0x0040)
    Start-Sleep -Milliseconds ([Math]::Max($WarmupMilliseconds, 800))

    $process.Refresh()
    if ($process.HasExited) {
        throw (New-FailureMessage "WinUI process exited after resized-window verification with code $($process.ExitCode).")
    }

    $freshHandle = Find-ProcessWindow -ProcessId $process.Id
    if ($freshHandle -ne [IntPtr]::Zero) {
        $windowHandle = $freshHandle
    }
    $rect = Get-WindowRectangle $windowHandle
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "PageTitle"
    Assert-AutomationElementExists -Handle $windowHandle -AutomationId "SegmentedModeBar"

    $resizedScreenshotPath = Join-Path $OutputDirectory "winui-runtime-$stamp-resized.png"
    $resizedMetricsPath = Join-Path $OutputDirectory "winui-runtime-$stamp-resized.json"
    $resizedBitmap = Save-WindowScreenshot -Rect $rect -Path $resizedScreenshotPath -Handle $windowHandle
    try {
        $resizedMetrics = Measure-VisualSurface -Bitmap $resizedBitmap
        Assert-VisualMetrics -Metrics $resizedMetrics
    } finally {
        $resizedBitmap.Dispose()
    }

    [ordered]@{
        screenshot = $resizedScreenshotPath
        requested = [ordered]@{
            width = $resizeWidth
            height = $resizeHeight
        }
        actual = [ordered]@{
            width = $rect.Width
            height = $rect.Height
        }
        metrics = $resizedMetrics
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resizedMetricsPath -Encoding UTF8

    Write-Host ("[OK] Resized-window UIA verified: PageTitle, SegmentedModeBar at {0}x{1}" -f $rect.Width, $rect.Height)
    Write-Host "[OK] Resized-window screenshot: $resizedScreenshotPath"
    Write-Host "[OK] Resized-window visual metrics: $resizedMetricsPath"
} catch {
    throw (New-FailureMessage $_.Exception.Message)
} finally {
    if ($process -and -not $KeepRunning) {
        $process.Refresh()
        if (-not $process.HasExited) {
            [void]$process.CloseMainWindow()
            if (-not $process.WaitForExit(3000)) {
                Stop-Process -Id $process.Id -Force
            }
        }
    }
}
