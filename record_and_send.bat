@echo off
setlocal enabledelayedexpansion

REM We set the Date and Webhook URL variables here. Make sure to change WEBHOOK_URL to your proper webhook URL!
set YYYYMMDD=%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%
set WEBHOOK_URL=https://discord.com/api/webhooks/***/***

REM Change "Game Capture HD60 S" and "Game Capture HD60 S Audio" to your respective capture device. The parameters of the command may need tweaking depending on your capture device. This recording will last exactly 5 minutes assuming it is not terminated by you before then.
start ffmpeg_wrap.exe ffmpeg -f dshow -i video="Game Capture HD60 S":audio="Game Capture HD60 S Audio" -bufsize 2G -framerate 60 -video_size 1920x1080 -map 0 -map 0:a -c:v libx264 -c:a aac C:\EAS_Alerts\%YYYYMMDD%-%random%%random%.mp4

REM Save SAME header to a temporary file.
echo %SAMEDEC_MSG%: > alert_temp.txt

REM https://stackoverflow.com/a/6362922
FOR /F "tokens=* USEBACKQ" %%F IN (`python dsame3/dsame.py --msg '%SAMEDEC_MSG%'`) DO (
SET var=%%F
)

REM I generated this portion of the code with ChatGPT. Make of that what you will, but it works, most importantly. It just takes the two independent lines in the alert log (the ZCZC header and the human readable text) and makes them into one line so Discord can receive it properly.
set file=alert_temp.txt
set line_number=1
set text_to_append=%var%

set content=
for /f "tokens=* USEBACKQ" %%a in (`type "%file%"`) do (
    set "line=%%a"
    if !line_number! equ 1 (
        set "line=!line!!text_to_append!"
    )
    set "content=!content!!line!"
)

echo !content! > "%file%"
REM End ChatGPT portion.

REM Save alert to log.
type alert_temp.txt >> alert_log.txt
set /p msg= < alert_temp.txt

REM Call curl to send the Discord message.
curl -H "Content-Type: application/json" -d "{\"username\": \"EAS Alerts\", \"content\":\"%msg%\", \"avatar_url\": \"https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/EAS_new.svg/888px-EAS_new.svg.png\"}" %WEBHOOK_URL%

REM Delete temporary alert file.
del /F /Q alert_temp.txt

REM Wait 300 seconds (5 minutes) before terminating recording.
ping 192.0.2.2 -n 1 -w 300000 > nul
taskkill /im ffmpeg_wrap.exe

REM Finally, exit.
exit