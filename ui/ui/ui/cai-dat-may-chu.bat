@echo off
rem Bien may nay thanh may chu LAN Chat: mo cong tuong lua, tu chay khi dang nhap Windows,
rem tin cay chung thu goc va bat may chu ngay. Chay lai file nay bat ky luc nao cung duoc.
title Cai dat may chu LAN Chat

rem Can quyen quan tri de mo cong trong tuong lua
net session >nul 2>&1
if errorlevel 1 (
  echo Can quyen quan tri. Windows se hoi xac nhan, hay bam Yes.
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "DIR=%~dp0"
set "SRV=%~dp0server.py"
echo.
echo [1/4] Mo cong 8443 trong tuong lua Windows...
netsh advfirewall firewall delete rule name="LAN Chat 8443" >nul 2>&1
netsh advfirewall firewall add rule name="LAN Chat 8443" dir=in action=allow protocol=TCP localport=8443 profile=private,public
if errorlevel 1 echo     Khong mo duoc cong. Hay mo cong 8443 bang tay trong Windows Defender Firewall.

echo [2/4] Dang ky may chu tu chay ngam moi khi dang nhap Windows...
powershell -NoProfile -Command "$a = New-ScheduledTaskAction -Execute 'pythonw.exe' -Argument ('\"' + $env:SRV + '\"') -WorkingDirectory $env:DIR; $t = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME; $s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; Register-ScheduledTask -TaskName 'LAN Chat Server' -Action $a -Trigger $t -Settings $s -Force | Out-Null"
if errorlevel 1 (echo     Khong dang ky duoc. Ban van co the bat may chu bang chay-may-chu.bat.) else (echo     Da dang ky: "LAN Chat Server" trong Task Scheduler.)

echo [3/4] Tin cay chung thu goc tren may nay (de Chrome het canh bao)...
if exist "%DIR%data\ca.pem" (
  certutil -user -addstore Root "%DIR%data\ca.pem" >nul
  if errorlevel 1 (echo     Ban da bo qua buoc nay.) else (echo     Da cai chung thu goc.)
) else (
  echo     Chua co chung thu. Se tao khi may chu chay lan dau; chay lai file nay sau.
)

echo [4/4] Bat may chu...
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://localhost:8000/api/health | Out-Null; '    May chu dang chay roi. Neu dang mo bang cua so den, co the dong cua so do; tu lan dang nhap sau may chu se tu chay ngam.' } catch { Start-ScheduledTask -TaskName 'LAN Chat Server'; Start-Sleep 4; try { $h = Invoke-RestMethod -TimeoutSec 4 http://localhost:8000/api/health; '    Da bat. Dia chi cho may khac cung Wi-Fi: https://' + $h.ip + ':8443/' } catch { '    Chua bat duoc. Xem nhat ky trong data\server.log' } }"

echo.
echo Xong. Tren may nay mo: http://localhost:8000/
echo Go bo: chay go-cai-dat-may-chu.bat
pause
