@echo off
REM %1 is the full path of the selected MP4 file

REM Remove quotes from path (in case)
set "input=%~1"

REM Get filename without extension
for %%F in ("%input%") do set "filename=%%~nF"
for %%F in ("%input%") do set "folder=%%~dpF"

REM Output path (same folder, mp3 extension)
set "output=%folder%%filename%.mp3"

REM Convert mp4 audio to mp3 using ffmpeg
ffmpeg -hide_banner -loglevel error -i "%input%" -vn -acodec libmp3lame -q:a 2 "%output%"

echo Converted "%input%" to "%output%"