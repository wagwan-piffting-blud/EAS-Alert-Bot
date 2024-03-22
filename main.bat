@ECHO OFF

REM Change your audio device here if you need to to whatever capture card you're using. As well, make sure to double check the sample rate passed to SAMEDec if you do.
ffmpeg -f dshow -i audio="Game Capture HD60 S Audio" -f wav pipe:1 | samedec -r 48000 -- "record_and_send.bat"