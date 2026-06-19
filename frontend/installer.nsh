; Request administrator privileges for the installer
; This ensures netsh firewall commands and .NET checks succeed without UAC prompts
RequestExecutionLevel admin

!macro customInstall
  ; ── Open required firewall ports ───────────────────────────────────────────
  DetailPrint "Opening firewall ports for UTAS..."

  ; Clean up any old rules first (safe on fresh install too)
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS ADMS Port"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-4370-TCP"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-4370-UDP"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-5001-TCP"'

  ; Port 4370 TCP — ZKTeco ADMS push receiver + API
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="UTAS-4370-TCP" dir=in action=allow protocol=TCP localport=4370 profile=any enable=yes'

  ; Port 4370 UDP — ZKTeco device keepalive / time sync
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="UTAS-4370-UDP" dir=in action=allow protocol=UDP localport=4370 profile=any enable=yes'

  ; Port 5001 TCP — FK Bridge internal HTTP (backend ↔ FkBridge.exe)
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="UTAS-5001-TCP" dir=in action=allow protocol=TCP localport=5001 profile=any enable=yes'

  DetailPrint "Firewall rules applied."
!macroend

!macro customUnInstall
  DetailPrint "Removing UTAS firewall rules..."
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS ADMS Port"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-4370-TCP"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-4370-UDP"'
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="UTAS-5001-TCP"'
  DetailPrint "Firewall rules removed."

  ; Clean up persistent installation flags so the next installation starts fresh
  DetailPrint "Cleaning up persistent security flags..."
  DeleteRegKey HKCU "Software\UTAS"
  Delete "$PROFILE\.utas_sec"
!macroend
