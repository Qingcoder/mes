@echo off
chcp 65001 >nul
title 配置 MES 手机局域网访问

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 正在请求管理员权限...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo ==========================================
echo   MES 手机局域网访问配置
echo ==========================================
echo.

netsh advfirewall firewall add rule name="MES 8007 LAN" dir=in action=allow protocol=TCP localport=8007 >nul 2>&1
netsh advfirewall firewall add rule name="MES 8010 LAN" dir=in action=allow protocol=TCP localport=8010 >nul 2>&1
echo [OK] 防火墙已放行 8007 / 8010

set "LANIP="
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | Select-Object -First 1).IPAddress"') do set "LANIP=%%i"

echo.
echo 请在手机浏览器打开：
if defined LANIP (
  echo   http://%LANIP%:8007/login
) else (
  echo   http://<电脑局域网IP>:8007/login
)
echo.
echo 手机需与电脑连接同一 Wi-Fi / 局域网。
echo 若打不开，请确认 8007 后端正在运行。
echo.
pause
