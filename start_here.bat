ffmpeg -i "dsame3\sample alert\WXR-RWT.ogg" -f wav pipe:1 | samedec -r 44100 -- %~dp0\record_and_send.bat