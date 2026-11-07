@echo off
rem Chia se may chu LAN Chat ra Internet de may dung 4G/5G hoac khac mang ket noi duoc.
rem Can chay chay-may-chu.bat truoc. Dong cua so nay la ngung chia se.
title Chia se LAN Chat ra Internet
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo Chua co cong cu cloudflared. Hay cai mot lan bang lenh:
  echo     winget install --id Cloudflare.cloudflared
  echo roi dong cua so nay va chay lai file.
  pause
  exit /b
)
echo Doi vai giay, tim dong co link dang https://....trycloudflare.com ben duoi.
echo Mo link do tren dien thoai 4G/5G, hoac nhap no vao nut "Ket noi may chu LAN".
echo Ai co link deu mo duoc trang dang ky. Chi gui link cho nguoi quen.
echo.
cloudflared tunnel --url http://localhost:8000
pause
