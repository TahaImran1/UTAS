# Test FkBridge connect + pull against an FK/AMF device (after verify_amf60_tcp.ps1 passes).
# Usage:
#   .\verify_fk_bridge_pull.ps1
#   .\verify_fk_bridge_pull.ps1 -DeviceIp 192.168.100.67 -License 1262

param(
    [string]$DeviceIp = "192.168.100.67",
    [int]$Port = 5005,
    [int]$MachineNo = 1,
    [int]$License = 1262,
    [int]$NetPassword = 0,
    [int]$TimeoutMs = 5000,
    [string]$BridgeUrl = $(if ($env:FK_BRIDGE_URL) { $env:FK_BRIDGE_URL } else { "http://127.0.0.1:5001" })
)

$ErrorActionPreference = "Stop"
$base = $BridgeUrl.TrimEnd("/")
$body = @{
    ip          = $DeviceIp
    port        = $Port
    machineNo   = $MachineNo
    license     = $License
    timeoutMs   = $TimeoutMs
    netPassword = $NetPassword
}

Write-Host "=== FkBridge pull verification ===" -ForegroundColor Cyan
Write-Host "Bridge: $base  Device: ${DeviceIp}:$Port  license=$License" -ForegroundColor Gray

Write-Host "`n1. Health..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 10
if (-not $health.dll_loaded) {
    Write-Host "FAIL: dll_loaded=false. Copy FKAttend.dll - run fk-bridge\copy-fk-dll.ps1" -ForegroundColor Red
    exit 1
}
Write-Host "   OK (dll loaded)" -ForegroundColor Green

Write-Host "`n2. Connect..." -ForegroundColor Cyan
$connect = Invoke-RestMethod -Method Post -Uri "$base/connect" -ContentType "application/json" -Body ($body | ConvertTo-Json) -TimeoutSec 30
if (-not $connect.success) {
    Write-Host "FAIL: $($connect.error) (handle=$($connect.handle))" -ForegroundColor Red
    Write-Host "Device must be Local mode, port 5005, SDK demo Open Comm must work first." -ForegroundColor Yellow
    exit 1
}
Write-Host "   OK (handle=$($connect.handle))" -ForegroundColor Green

Write-Host ""
Write-Host "3. Pull - read only, no clear..." -ForegroundColor Cyan
$pull = Invoke-RestMethod -Method Post -Uri "$base/pull" -ContentType "application/json" -Body ($body | ConvertTo-Json) -TimeoutSec 120
if (-not $pull.success) {
    Write-Host "FAIL: $($pull.error)" -ForegroundColor Red
    exit 1
}
$count = if ($null -ne $pull.count) { $pull.count } else { @($pull.logs).Count }
Write-Host "   OK - $count log record(s)" -ForegroundColor Green
if ($count -gt 0 -and $pull.logs) {
    $pull.logs | Select-Object -First 3 | ForEach-Object { Write-Host "   sample: user=$($_.userId) time=$($_.timestamp)" }
}

Write-Host "`n4. UTAS: ensure machines.json has driver=fk, protocol=TCP, sn=AMT602511730" -ForegroundColor Cyan
Write-Host "   Run manual pull or wait for scheduler; check GET /pull/fk-bridge/health" -ForegroundColor Gray
Write-Host "`nAll FkBridge checks passed." -ForegroundColor Green
exit 0
