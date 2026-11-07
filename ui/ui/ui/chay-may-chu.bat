@echo off
rem Bat may chu LAN Chat. Giu cua so nay mo trong luc dung app; dong cua so la tat may chu.
cd /d "%~dp0"
title May chu LAN Chat
python server.py
echo.
echo May chu da dung. Neu bao loi "address already in use", hay tat cua so may chu cu roi chay lai.
pause
