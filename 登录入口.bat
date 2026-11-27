@echo off
chcp 65001 >nul
title Daimon MES - Login
echo Opening Daimon MES login page ...
echo If it does not open, run StartBackend.bat first.
start "" "http://127.0.0.1:8007/login"
