# Copy FKAttend.dll and FKModelDic.ini into FkBridge publish folder after dotnet publish.
# Run from repo root or fk-bridge folder.

param(
    [string]$VendorDllDir = "",
    [string]$PublishDir = ""
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $PublishDir) {
    $PublishDir = Join-Path $scriptRoot "FkBridge\bin\Release\net8.0\win-x86\publish"
}

if (-not $VendorDllDir) {
    $candidates = @(
        (Join-Path $scriptRoot "libs\win-x86"),
        "E:\Projects\DFace_C#_202006\dll",
        (Join-Path (Split-Path $scriptRoot -Parent) "..\DFace_C#_202006\dll"),
        (Join-Path $env:USERPROFILE "Downloads"),
        (Join-Path $scriptRoot "FkBridge")
    )
    foreach ($c in $candidates) {
        $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($c)
        if (Test-Path (Join-Path $resolved "FKAttend.dll")) {
            $VendorDllDir = $resolved
            break
        }
    }
}

if (-not (Test-Path $PublishDir)) {
    Write-Error "Publish folder not found: $PublishDir`nRun: dotnet publish -c Release -r win-x86 (from fk-bridge\FkBridge)"
}

if (-not $VendorDllDir -or -not (Test-Path (Join-Path $VendorDllDir "FKAttend.dll"))) {
    Write-Error "FKAttend.dll not found. Set -VendorDllDir to your SDK dll folder (e.g. DFace_C#_202006\dll)."
}

New-Item -ItemType Directory -Force -Path $PublishDir | Out-Null
$files = @(
    "FKAttend.dll",
    "FKModelDic.ini",
    "FK623Attend.dll",
    "FKPwdEncDec.dll",
    "FKPwdCardEncDec.dll",
    "FaceDataConv.dll",
    "FpDataConv.dll",
    "AxInterop.AXIMAGELib.dll",
    "AxInterop.RealSvrOcxTcpLib.dll",
    "Interop.AXIMAGELib.dll",
    "Interop.RealSvrOcxTcpLib.dll",
    "FKAttend__.dll",
    "FKDataFile_FKL103OF50.dll",
    "FKViaDev.dll",
    "IOTCAPIs.dll",
    "ImageIO.dll",
    "LFWViaDev.dll",
    "mfc100.dll",
    "adodb.dll"
)
foreach ($f in $files) {
    $src = Join-Path $VendorDllDir $f
    if (Test-Path $src) {
        try {
            Copy-Item -Path $src -Destination (Join-Path $PublishDir $f) -Force -ErrorAction Stop
            Write-Host "Copied $f -> $PublishDir"
        } catch {
            Write-Warning "Could not copy $f (file in use?): $($_.Exception.Message)"
        }
    } else {
        # Only warn for core files
        if ($f -eq "FKAttend.dll" -or $f -eq "FKModelDic.ini") {
            Write-Warning "Missing $src"
        }
    }
}

Write-Host "Done. Verify: Invoke-RestMethod http://127.0.0.1:5001/health (dll_loaded should be true)"
