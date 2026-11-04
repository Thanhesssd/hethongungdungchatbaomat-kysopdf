@echo off
rem Cai chung chi goc LAN Chat cho tai khoan Windows nay, de Chrome khong con canh bao.
echo Windows se hoi xac nhan. Hay bam Yes.
certutil -user -addstore Root "%~dp0data\ca.pem"
echo.
echo Xong. Hay tat han Chrome roi mo lai.
pause
