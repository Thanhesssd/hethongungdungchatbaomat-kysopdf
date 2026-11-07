@echo off
rem Go bo cai dat may chu LAN Chat: tat may chu chay ngam, bo tu chay, dong cong tuong lua.
rem Khong xoa tai khoan va tin nhan trong thu muc data.
title Go cai dat may chu LAN Chat
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -Command "Stop-ScheduledTask -TaskName 'LAN Chat Server' -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName 'LAN Chat Server' -Confirm:$false -ErrorAction SilentlyContinue"
netsh advfirewall firewall delete rule name="LAN Chat 8443" >nul 2>&1
echo Da go: may chu khong con tu chay va cong 8443 da dong.
echo Du lieu trong thu muc data van duoc giu nguyen.
pause
