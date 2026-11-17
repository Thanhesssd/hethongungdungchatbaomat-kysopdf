@echo off
rem Cai dia chi Internet CO DINH cho may chu LAN Chat (Cloudflare Named Tunnel + ten mien rieng).
rem Lam mot lan. Sau do chia-se-internet.bat dung dia chi co dinh, ma QR da gui khong bi het han.
rem Can: tai khoan Cloudflare (mien phi) va mot ten mien da tro nameserver ve Cloudflare.
chcp 65001 >nul
title Cai dia chi co dinh cho LAN Chat
cd /d "%~dp0"

where cloudflared >nul 2>&1
if errorlevel 1 (
  echo Chua co cloudflared. Cai mot lan bang lenh:  winget install --id Cloudflare.cloudflared
  pause
  exit /b 1
)

echo.
echo Buoc 1/4: Dang nhap Cloudflare (trinh duyet se mo, chon ten mien cua ban)...
cloudflared tunnel login
if errorlevel 1 goto loi

set "TUNNEL=lanchat"
set /p TUNNEL=Ten duong ham [lanchat]:
set "HOST="
set /p HOST=Dia chi muon dung, vi du chat.tenmien.com:
if "%HOST%"=="" (
  echo Chua nhap dia chi.
  goto loi
)

echo.
echo Buoc 2/4: Tao duong ham "%TUNNEL%" (da co thi bo qua)...
cloudflared tunnel create %TUNNEL%

echo Buoc 3/4: Tro %HOST% ve duong ham...
cloudflared tunnel route dns %TUNNEL% %HOST%
if errorlevel 1 goto loi

echo Buoc 4/4: Luu cau hinh cho may chu va chia-se-internet.bat...
setx LANCHAT_TUNNEL "%TUNNEL%" >nul
setx LANCHAT_PUBLIC_URL "https://%HOST%" >nul

echo.
echo Xong. Dia chi co dinh: https://%HOST%
echo  - Khoi dong lai may chu (hoac dang xuat Windows roi dang nhap lai) de may chu nhan dia chi moi.
echo  - Chay chia-se-internet.bat: dia chi duoc ghi vao may-chu.json mot lan va day len GitHub.
echo  - Luu y: laptop van la may chu, phai bat va khong ngu thi may khac moi vao duoc.
pause
exit /b 0

:loi
echo.
echo Chua cai xong. Kiem tra ten mien da them vao Cloudflare chua, roi chay lai file nay.
pause
exit /b 1
