@echo off
setlocal enabledelayedexpansion

for /R "data\raw" %%F in (*) do (
    set "dir=%%~dpF"
    set "fname=%%~nF"
    set "ext=%%~xF"
    set "temp=!dir!!fname!_44100!ext!"
    ffmpeg -y -i "%%F" -ar 44100 "!temp!"
    move /Y "!temp!" "%%F"
)