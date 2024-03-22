# EAS Alert Bot

_What_ is this?
---
This is a small bot for recording and relaying, in near real time, United States Emergency Alert System alerts to a Discord webhook, using the [SAMEDec](https://lib.rs/crates/samedec) Rust package, ffmpeg, cURL, and [dsame3](https://github.com/jamieden/dsame3). This is how it works (roughly):

1. Listens for EAS tones from an input using ffmpeg, meaning the input can be anything, either attached to your local computer you're running the bot on (something like a capture card) or an external source (such as a live audio stream).
2. Receives the EAS tones using SAMEDec.
3. Records the EAS alert using ffmpeg (to the directory `C:\EAS_Alerts`).
4. Sends the demodulated header to dsame3 for a human-readable message.
5. Sends the header AND human-readable message to Discord via a simple cURL request.
6. Logs the received alert to a central file (`alert_log.txt` in the directory you're running the bot from).

_Why_?
---
Like a (somewhat surprising) number of other people, I am interested in the concept of the EAS and civil defense broadcasting in general. Any way to relay alerts like this, in (almost) real time no less, is especially interesting and cool to me personally.

_How_ to install it?
---
The recommended way to install everything is via [Chocolatey](https://chocolatey.org/install), a Windows-based package manager. (Did I mention this whole thing was built with Windows in mind?)

Steps:

1. Install Chocolatey from the link above.
2. Run the following command to get all the pre-requisite software: `choco install ffmpeg curl rust python3`.
3. Further install SAMEDec by running `cargo install samedec`.
4. Install the requirements for dsame3 by going into the dsame3 folder and running `pip install -r requirements.txt`.
5. Edit record_and_send.bat AND main.bat to add your webhook and capture method's information. More info on this step is in the **wiki**.
6. Run start_here.bat. This file will only need to be run once, to test everything and download the models for dsame3. Assuming you see a message in Discord and something recorded from your preferred capture device, you're good to go for the final step:
7. Add a scheduled task in Task Scheduler. Once this is done, this bot will run on boot and run in the background silently. More info on this step in the **wiki**.

_Disclaimers_
---
Like SAMEDec and dsame3's README's state: **THIS BOT IS NOT FOR USE IN SAFETY-CRITICAL APPLICATIONS WHERE IT COULD MEAN INJURY OR DEATH MAY OCCUR!!! ALWAYS, ALWAYS, ALWAYS HAVE MULTIPLE METHODS TO RECEIVE EMERGENCY ALERTS.** Think of this bot ONLY as a fun little toy, NOT a proper EAS ENDEC to alert the public in life-threatening situations.

_Who_ am I?
---
I'm Wags, and I make a variety of things for the Internet. You can find my personal website [here](https://wagspuzzle.space/). I even have a blog (BlARG) post about the EAS [located here](https://wagspuzzle.space/blarg/2023-03-09-eas/) for your perusal.