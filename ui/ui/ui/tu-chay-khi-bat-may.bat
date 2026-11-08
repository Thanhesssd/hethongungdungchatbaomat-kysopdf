@echo off
rem Cho may chu LAN Chat tu chay ngam moi khi dang nhap Windows va tu bat lai neu bi tat.
rem Khong can quyen quan tri. Go bo: chay go-tu-chay-khi-bat-may.bat
cd /d "%~dp0"
set "VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\LAN Chat may chu.vbs"
> "%VBS%" echo CreateObject("WScript.Shell").Run "pythonw ""%~dp0giu_may_chu.pyw""", 0, False
echo Da cai: may chu se tu chay moi khi dang nhap Windows.
start "" pythonw "%~dp0giu_may_chu.pyw"
echo May chu dang chay ngam. Tren may nay mo: http://localhost:8000/
timeout /t 5 >nul
