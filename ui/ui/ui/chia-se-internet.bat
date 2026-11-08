@echo off
rem Chia se may chu LAN Chat ra Internet de may dung 4G/5G hoac khac mang ket noi duoc.
rem Can chay may chu truoc (chay-may-chu.bat hoac cai-dat-may-chu.bat). Dong cua so nay la ngung chia se.
title Chia se LAN Chat ra Internet
cd /d "%~dp0"
python chia_se_internet.py
pause
