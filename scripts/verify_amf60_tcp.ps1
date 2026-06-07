# Verify AMF60 / FK device TCP readiness (port 5005) per AMF-60 user manual SetComm.
# Usage (from cmd.exe use verify_amf60_tcp.bat — .ps1 may open in Notepad):
#   verify_amf60_tcp.bat 192.168.100.67
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_amf60_tcp.ps1 -DeviceIp 192.168.100.67

param(
    [string]$DeviceIp = "192.168.100.67",
    [int]$Port = 5005
)

$ErrorActionPreference = "Continue"
Write-Host "=== AMF60 TCP verification ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Device checklist (on terminal: MENU > SetComm):" -ForegroundColor Yellow
Write-Host "  1. Ethernet: IP matches machines.json; Port NO. = 5005 (do not change per manual)"
Write-Host "  2. Net Mode: Local = SDK/TCP pull; Internet = HTTP push only"
Write-Host "  3. TCP/IP option must have been ordered from supplier (not addable on client side)"
Write-Host "  4. Vendor SDK demo Open Comm must succeed before UTAS/FkBridge pull"
Write-Host ""

Write-Host "Testing TCP ${DeviceIp}:${Port} ..." -ForegroundColor Cyan
$tnc = Test-NetConnection -ComputerName $DeviceIp -Port $Port -WarningAction SilentlyContinue
if ($tnc.TcpTestSucceeded) {
    Write-Host "  TCP port OPEN" -ForegroundColor Green
} else {
    Write-Host "  TCP port CLOSED or unreachable" -ForegroundColor Red
    Write-Host "  Fix: Set Net Mode=Local, confirm TCP hardware option, firewall, same subnet."
    exit 1
}

Write-Host ""
Write-Host "FkBridge health (optional):" -ForegroundColor Cyan
$bridgeUrl = $env:FK_BRIDGE_URL
if (-not $bridgeUrl) { $bridgeUrl = "http://127.0.0.1:5001" }
try {
    $health = Invoke-RestMethod -Uri "$bridgeUrl/health" -TimeoutSec 5
    if ($health.dll_loaded) {
        Write-Host "  FkBridge reachable, FKAttend.dll loaded" -ForegroundColor Green
    } else {
        Write-Host "  FkBridge reachable but dll_loaded=false - run fk-bridge\copy-fk-dll.ps1" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  FkBridge not running at $bridgeUrl - start FkBridge.exe first for SDK connect test." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next: .\verify_fk_bridge_pull.ps1 -DeviceIp $DeviceIp" -ForegroundColor Cyan
exit 0
