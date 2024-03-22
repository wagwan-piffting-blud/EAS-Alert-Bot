# Copyright (C) 2017 Joseph W. Metcalf
# Modified by James Kitchens 2023
#
# Modifications include, but are not limited to, adding multiple language options,
# adding recording features for alerts, implementation of the Mexico SASMEX alert system,
# adding missing data to the ICAO list, implementing proper country detection, implementation of audio transcription,
# and Python 3.x compatibility.
#
# Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby
# granted, provided that the above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL,
# DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE
# USE OR PERFORMANCE OF THIS SOFTWARE.
#

# dependencies = subprocess.Popen(['python', 'pipDepend.py'], creationflags=subprocess.CREATE_NEW_CONSOLE)
# dependencies.wait()

# IMPLEMENT CONFIGURATION FILE TO AVOID REQUIRING THE USER TO CALL WITH ARGUMENTS
# JUST REPLACE THE ARGS WITH THE CONFIG FILE DATA VARIABLES

import multiprocessing
import platform
import sys
from tqdm import tqdm
import defs
import argparse
import string
import logging
import datetime
import subprocess
import sounddevice as sd
import soundfile as sf
import numpy as np
import os.path
from faster_whisper import WhisperModel
import time
import shutil
import urllib.request
from urllib import request
from zipfile import ZipFile

# Constants
SAMPLE_RATE = 44100  # Sample rate (Hz)
CHANNELS = 2  # Number of audio channels
FILE_NAME = 'recording.wav'  # Output file name
FILE_NAME_PATH = ''

# Recording state
is_recording = 0
file = None
stream = None
same1 = None
message1 = None

# Callback function for audio input
recorded_frames = []
MODEL_PATH = os.path.join(os.path.abspath(''), 'Model')
RESTART_QUEUE = False

eventWarning = ["AVW", "BHW", "BWW", "BZW", "CDW", "CEM", "CFW", "CHW", "CWW", "DBW", "DEW", "DSW", "EAN", "EQW", "EVI",
                "EWW", "FCW", "FFW", "FLW", "FRW", "FSW", "FZW", "HMW", "HUW", "HWW", "IBW", "IFW", "LAE", "LEW", "LSW",
                "NUW", "RHW", "SMW", "SPW", "SSW", "SVR", "TOR", "TRW", "TSW", "VOW", "WFW", "WSW", "SQW"]
eventWatch = ["AVA", "CFA", "DBA", "EVA", "FFA", "FLA", "HUA", "HWA", "SSA", "SVA", "TOA", "TRA", "TSA", "WFA", "WSA"]
eventAdvisory = ["ADR", "CAE", "DMO", "EAT", "FFS", "FLS", "HLS", "NAT", "NIC", "NMN", "NPT", "NST", 'POS', "RMT",
                 "RWT", "SPS", "SVS", "TOE"]
EEE2 = ''


def my_hook(t):
    last_b = [0]

    def update_to(b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            t.total = tsize
        t.update((b - last_b[0]) * bsize)
        last_b[0] = b

    return update_to


class TqdmUpTo(tqdm):
    """Alternative Class-based version of the above.
    Provides `update_to(n)` which uses `tqdm.update(delta_n)`.
    Inspired by [twine#242](https://github.com/pypa/twine/pull/242),
    [here](https://github.com/pypa/twine/commit/42e55e06).
    """

    def update_to(self, b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)  # will also set self.n = b * bsize


# NEED TO IMPLEMENT (maybe) SoX
# Multimon-NG might be an issue for MacOS
# IMPLEMENT ERROR FLAG SO PROGRAM PAUSES INSTEAD OF WAITING 5 SECONDS


# noinspection PyBroadException
def internet_on():
    try:
        request.urlopen('https://google.com', timeout=4)
        return True
    except Exception:
        return False


def os_clear():
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')


# noinspection PyBroadException
def dependency_check_rtl():
    if internet_on():
        PLATFORM = platform.system()
        if PLATFORM == 'Windows':
            home_directory = os.path.expanduser('~')
            # check if RTL-SDR exists or not
            try:
                subprocess.Popen('rtl_fm -h', stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                #sys.stdout.write('RTL-SDR is installed. \n')
            except Exception:
                if not os.path.exists(os.path.abspath('') + '\\Temp'):
                    os.makedirs(os.path.abspath('') + '\\Temp')
                # sys.stdout.write("Downloading RTL-SDR Windows Binary ZIP File. \n")
                with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                              desc='Downloading RTL-SDR Windows Binary ZIP File', ascii=' █') as t:
                    urllib.request.urlretrieve(
                        url="https://github.com/rtlsdrblog/rtl-sdr-blog/releases/download/1.01/Release.zip",
                        filename=os.path.abspath('') + '\\Temp\\Release.zip',
                        reporthook=t.update_to)
                if not os.path.exists(home_directory + '\\rtl-sdr-release'):
                    os.makedirs(home_directory + '\\rtl-sdr-release')
                with ZipFile(os.path.abspath('') + '\\Temp\\Release.zip', 'r') as zObject:
                    zObject.extractall(path=home_directory + '\\rtl-sdr-release')
                p = subprocess.Popen(["powershell.exe", '$PATH = [Environment]::GetEnvironmentVariable("PATH", '
                                                        '"User"); $new_path = "' + home_directory +
                                      '\\rtl-sdr-release\\"; if( $PATH -notlike "*"+$new_path+"*" ){ ['
                                      'Environment]::SetEnvironmentVariable("PATH", "$PATH;$new_path", '
                                      '"User")}'])
                p.communicate()
                shutil.rmtree(os.path.abspath('') + '\\Temp')
                global RESTART_QUEUE
                RESTART_QUEUE = True
        elif PLATFORM == 'Linux':
            sys.stdout.write(PLATFORM)
            try:
                os.system('sudo apt install rtl-sdr gqrx-sdr')
                # RESTART_QUEUE = True
            except Exception as e:
                sys.stdout.write(str(e) + '\n')
        elif PLATFORM == 'Darwin':
            sys.stdout.write(PLATFORM)
            os.system('brew install --cask gqrx')
            os.system('brew install librtlsdr')
        else:
            sys.stdout.write('UNEXPECTED ERROR. \n')
    else:
        sys.stdout.write('RTL-SDR DEPENDENCY CHECK ERROR: This device seems disconnected from the internet. '
                         'Dependency checks cannot be conducted. This may cause unexpected program '
                         'behavior. Please connect your device to the internet as soon as possible to '
                         'ensure all dependencies are properly installed. \n')


# noinspection PyBroadException
def dependency_check_ffmpeg():
    if internet_on():
        PLATFORM = platform.system()
        if PLATFORM == 'Windows':
            # sys.stdout.write(PLATFORM + '\n')
            home_directory = os.path.expanduser('~')
            # check if FFMPEG exists or not
            try:
                subprocess.Popen('ffmpeg -h', stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                #sys.stdout.write('FFMPEG is installed. \n')
            except Exception:
                if not os.path.exists(os.path.abspath('') + '\\Temp'):
                    os.makedirs(os.path.abspath('') + '\\Temp')
                # sys.stdout.write("Downloading FFMPEG Windows Binary ZIP File. \n")
                with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                              desc='Downloading FFMPEG Windows Binary ZIP File', ascii=' █') as t:
                    urllib.request.urlretrieve(
                        url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64"
                            "-gpl.zip",
                        filename=os.path.abspath('') + '\\Temp\\ffmpeg-master-latest-win64-gpl.zip',
                        reporthook=t.update_to)
                # if not os.path.exists(home_directory + '\\ffmpeg'):
                #     os.makedirs(home_directory + '\\ffmpeg')
                with ZipFile(os.path.abspath('') + '\\Temp\\ffmpeg-master-latest-win64-gpl.zip', 'r') as zObject:
                    zObject.extractall(path=home_directory)
                os.rename(home_directory + '\\ffmpeg-master-latest-win64-gpl', home_directory + '\\ffmpeg')
                p = subprocess.Popen(["powershell.exe", '$PATH = [Environment]::GetEnvironmentVariable("PATH", '
                                                        '"User"); $new_path = "' + home_directory +
                                      '\\ffmpeg\\bin\\"; if( $PATH -notlike "*"+$new_path+"*" ){ ['
                                      'Environment]::SetEnvironmentVariable("PATH", "$PATH;$new_path", '
                                      '"User")}'])
                p.communicate()
                # os.environ["PATH"] += os.pathsep + home_directory + '\\ffmpeg\\bin;'
                shutil.rmtree(os.path.abspath('') + '\\Temp')
                global RESTART_QUEUE
                RESTART_QUEUE = True
        elif PLATFORM == 'Linux':
            sys.stdout.write(PLATFORM)
            try:
                os.system('sudo apt install ffmpeg')
                # RESTART_QUEUE = True
            except Exception as e:
                sys.stdout.write(str(e) + '\n')
        elif PLATFORM == 'Darwin':
            sys.stdout.write(PLATFORM)
            os.system('brew install ffmpeg')
        else:
            sys.stdout.write('UNEXPECTED ERROR. \n')
    else:
        sys.stdout.write('FFMPEG DEPENDENCY CHECK ERROR: This device seems disconnected from the internet. '
                         'Dependency checks cannot be conducted. This may cause unexpected program '
                         'behavior. Please connect your device to the internet as soon as possible to '
                         'ensure all dependencies are properly installed. \n')


# noinspection PyBroadException
def dependency_check_multimon():
    if internet_on():
        PLATFORM = platform.system()
        if PLATFORM == 'Windows':
            # sys.stdout.write(PLATFORM + '\n')
            home_directory = os.path.expanduser('~')
            # check if Multimon-NG exists or not
            try:
                subprocess.Popen('multimon-ng -h', stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                #sys.stdout.write('Multimon-NG is installed. \n')
            except Exception:
                if not os.path.exists(os.path.abspath('') + '\\Temp'):
                    os.makedirs(os.path.abspath('') + '\\Temp')
                # sys.stdout.write("Downloading Multimon-NG Windows Binary ZIP File. \n")
                with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                              desc='Downloading Multimon-NG Windows Binary ZIP File', ascii=' █') as t:
                    urllib.request.urlretrieve(
                        url="https://github.com/cuppa-joe/multimon-ng/releases/download/WIN32-0415/multimon-ng-WIN32"
                            ".zip",
                        filename=os.path.abspath('') + '\\Temp\\multimon-ng-WIN32.zip',
                        reporthook=t.update_to)
                if not os.path.exists(home_directory + '\\multimon-ng'):
                    os.makedirs(home_directory + '\\multimon-ng')
                with ZipFile(os.path.abspath('') + '\\Temp\\multimon-ng-WIN32.zip', 'r') as zObject:
                    zObject.extractall(path=home_directory + '\\multimon-ng')
                p = subprocess.Popen(["powershell.exe", '$PATH = [Environment]::GetEnvironmentVariable("PATH", '
                                                        '"User"); $new_path = "' + home_directory +
                                      '\\multimon-ng\\"; if( $PATH -notlike "*"+$new_path+"*" ){ ['
                                      'Environment]::SetEnvironmentVariable("PATH", "$PATH;$new_path", '
                                      '"User")}'])
                p.communicate()
                shutil.rmtree(os.path.abspath('') + '\\Temp')
                global RESTART_QUEUE
                RESTART_QUEUE = True
        elif PLATFORM == 'Linux':
            sys.stdout.write(PLATFORM)
            try:
                os.system('sudo apt install multimon-ng')
                # RESTART_QUEUE = True
            except Exception as e:
                sys.stdout.write(str(e) + '\n')
        elif PLATFORM == 'Darwin':
            sys.stdout.write(PLATFORM)
        else:
            sys.stdout.write('UNEXPECTED ERROR. \n')
    else:
        sys.stdout.write('MULTIMON-NG DEPENDENCY CHECK ERROR: This device seems disconnected from the internet. '
                         'Dependency checks cannot be conducted. This may cause unexpected program '
                         'behavior. Please connect your device to the internet as soon as possible to '
                         'ensure all dependencies are properly installed. \n')


def dependency_check_model(MODEL_NAME):
    if internet_on():
        if not os.path.exists(os.path.join(MODEL_PATH, MODEL_NAME)):
            sys.stdout.write("Model path does not exist for " + MODEL_NAME + ". Creating folders and downloading files. \n")
            os.makedirs(os.path.join(MODEL_PATH, MODEL_NAME))
        if not os.path.exists(os.path.join(MODEL_PATH, MODEL_NAME, 'model.bin')):
            # sys.stdout.write("Downloading model.bin for model " + MODEL_NAME + ". \n")
            with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                          desc="Downloading model.bin for model " + MODEL_NAME, ascii=' █') as t:
                urllib.request.urlretrieve(
                    url="https://huggingface.co/guillaumekln/faster-whisper-" + MODEL_NAME + "/resolve/main/model.bin",
                    filename=os.path.join(MODEL_PATH, MODEL_NAME, 'model.bin'),
                    reporthook=t.update_to)
        if not os.path.exists(os.path.join(MODEL_PATH, MODEL_NAME, 'config.json')):
            # sys.stdout.write("Downloading config.json for model " + MODEL_NAME + ". \n")
            with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                          desc="Downloading config.json for model " + MODEL_NAME, ascii=' █') as t:
                urllib.request.urlretrieve(
                    url="https://huggingface.co/guillaumekln/faster-whisper-" + MODEL_NAME + "/resolve/main/config.json",
                    filename=os.path.join(MODEL_PATH, MODEL_NAME, 'config.json'),
                    reporthook=t.update_to)
        if not os.path.exists(os.path.join(MODEL_PATH, MODEL_NAME, 'tokenizer.json')):
            # sys.stdout.write("Downloading tokenizer.json for model " + MODEL_NAME + ". \n")
            with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                          desc="Downloading tokenizer.json for model " + MODEL_NAME, ascii=' █') as t:
                urllib.request.urlretrieve(
                    url="https://huggingface.co/guillaumekln/faster-whisper-" + MODEL_NAME + "/resolve/main/tokenizer.json",
                    filename=os.path.join(MODEL_PATH, MODEL_NAME, 'tokenizer.json'),
                    reporthook=t.update_to)
        if not os.path.exists(os.path.join(MODEL_PATH, MODEL_NAME, 'vocabulary.txt')):
            # sys.stdout.write("Downloading vocabulary.txt for model " + MODEL_NAME + ". \n")
            with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                          desc="Downloading vocabulary.txt for model " + MODEL_NAME, ascii=' █') as t:
                urllib.request.urlretrieve(
                    url="https://huggingface.co/guillaumekln/faster-whisper-" + MODEL_NAME + "/resolve/main/vocabulary.txt",
                    filename=os.path.join(MODEL_PATH, MODEL_NAME, 'vocabulary.txt'),
                    reporthook=t.update_to)
        #sys.stdout.write('All dependencies are installed and up to date for model ' + MODEL_NAME + '. \n')
    else:
        sys.stdout.write(MODEL_NAME + 'MODEL DEPENDENCY CHECK ERROR: This device seems disconnected from the internet. '
                                      'Dependency checks cannot be conducted. This may cause unexpected program '
                                      'behavior. Please connect your device to the internet as soon as possible to '
                                      'ensure all dependencies are properly installed. \n')


# noinspection PyUnusedLocal
def callback(indata, data, frames, status):
    recorded_frames.append(indata.copy())


# noinspection PyUnusedLocal,PyShadowingNames
def callback1(indata, outdata, frames, time, status):
    if status:
        print(status)
    outdata[:] = indata


def set_is_recording(data):
    global is_recording
    is_recording = data


def get_is_recording():
    global is_recording
    is_recording = is_recording
    return str(is_recording)


def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def transcribe_alert_faster(transcribe_path, transcription_model, message, FILE_NAME_PATH_LOCAL1, FILE_NAME_LOCAL,
                            message12, lang, compute, beam, device):
    start_time = time.time()
    global MODEL_PATH
    sys.stdout.write('Transcription started. \n')
    if transcription_model == 'large':
        transcription_model = str(transcription_model) + '-v2'
    FILE_NAME_PATH_LOCAL = os.path.abspath(FILE_NAME_PATH_LOCAL1)
    logging.debug(compute + '\n')
    logging.debug(str(beam) + '\n')
    logging.debug(device + '\n')
    if lang.upper() == 'EN' and not str(transcription_model) == 'large-v2':
        model = WhisperModel(model_size_or_path=str(os.path.join(MODEL_PATH, str(transcription_model) + '.en')),
                             device=device, compute_type=compute)
    else:
        model = WhisperModel(model_size_or_path=str(os.path.join(MODEL_PATH, str(transcription_model))), device=device,
                             compute_type=compute)
    segments, info = model.transcribe(os.path.join(FILE_NAME_PATH_LOCAL, FILE_NAME_LOCAL), beam_size=beam)
    logging.debug("Detected language '%s' with probability %f" % (info.language, info.language_probability))
    text = ''
    for segment in segments:
        text = text + " " + segment.text
    text = text.replace('.  ', '.\n')
    text = text.replace('  ', ' ')
    text = text.replace(' ', '', 1)
    TRANSCRIBE_NAME = os.path.join(str(transcribe_path[0]), FILE_NAME_LOCAL.replace('.wav', '.txt'))
    # noinspection PyBroadException
    try:
        with open(file=TRANSCRIBE_NAME, mode='x') as f:
            f.write(str(message + '\n\n' + message12 + '\n\n\n' + text))
            f.close()
        sys.stdout.write('Transcription Complete!!\n')
    except Exception as e:
        sys.stdout.write(
            'Error. Transcription could not be saved. Please check your path and make sure it is '
            'correct and you have access. Error: ' + str(e) + '\n')
    logging.debug("--- %s seconds ---" % (time.time() - start_time))


def set_FILE_NAME(alert, path):
    global FILE_NAME, FILE_NAME_PATH
    current_dateTime = datetime.datetime.now()
    event = defs.SAME__EEE[alert]
    event = event.replace(' ', '-')
    FILE_NAME = str(current_dateTime.strftime("%m")) + '-' + str(current_dateTime.strftime("%d")) + '-' + \
                str(current_dateTime.strftime("%Y")) + '_' + str(current_dateTime.strftime("%I")) + '-' + \
                str(current_dateTime.strftime("%M")) + '-' + str(current_dateTime.strftime("%p")) + '_' + \
                str(event) + '.wav'
    FILE_NAME_PATH = os.path.join(str(path[0]) + '\\')


def alert_start(JJJHHMM, format1='%j%H%M'):
    import calendar
    """Convert EAS date string to datetime format"""
    utc_dt = datetime.datetime.strptime(JJJHHMM, format1).replace(datetime.datetime.now(datetime.UTC).year)
    timestamp = calendar.timegm(utc_dt.timetuple())
    return datetime.datetime.fromtimestamp(timestamp)


def fn_dt(dt, format1='%I:%M %p'):
    """Return formated datetime"""
    return dt.strftime(format1)


# ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-

def format_error(info=''):
    logging.warning(' '.join(['INVALID FORMAT', info]))


def time_str(x, type1='hour'):
    if x == 1:
        return ''.join([str(x), ' ', type1])
    elif x >= 2:
        return ''.join([str(x), ' ', type1, 's'])


def get_length(TTTT):
    hh, mm = TTTT[:2], TTTT[2:]
    return ' '.join(filter(None, (time_str(int(hh)), time_str(int(mm), type1='minute'))))


def county_decode(input1, COUNTRY, LANG):
    """Convert SAME county/geographic code to text list"""
    P, SS, CCC, SSCCC = input1[:1], input1[1:3], input1[3:], input1[1:]
    if COUNTRY == 'US':
        if SSCCC in defs.SAME_CTYB:
            SAME__LOC = defs.SAME_LOCB
        else:
            SAME__LOC = defs.SAME_LOCA
        if CCC == '000':
            if LANG == 'EN':
                county = 'ALL'
            else:
                county = 'TODOS'
        else:
            county = defs.US_SAME_CODE[SSCCC]
        return [' '.join(filter(None, (SAME__LOC[P], county))), defs.US_SAME_AREA[SS]]
    elif COUNTRY == 'MX':
        if SSCCC in defs.SAME_CTYB:
            # noinspection PyUnusedLocal
            SAME__LOC = defs.SAME_LOCB
        else:
            SAME__LOC = defs.SAME_LOCA
            if CCC == '000':
                if LANG == 'EN':
                    county = 'COUNTRYWIDE'
                else:
                    county = 'EN TODO EL PAIS'
            else:
                county = defs.MX_SAME_CODE[SSCCC]
            return [' '.join(filter(None, (SAME__LOC[P], county))), defs.MX_SAME_AREA[SS]]
    else:
        if CCC == '000':
            if LANG == 'EN':
                county = 'ALL'
            else:
                county = 'TODOS'
        else:
            county = defs.CA_SAME_CODE[SSCCC]
        return [county, defs.CA_SAME_AREA[SS]]


def get_division(input1, COUNTRY='US', LANG='EN'):
    if COUNTRY == 'US':
        # noinspection PyBroadException
        try:
            DIVISION = defs.FIPS_DIVN[input1]
            if not DIVISION:
                DIVISION = 'areas'
        except:
            DIVISION = 'counties'
    elif COUNTRY == 'MX':
        if LANG == 'EN':
            # noinspection PyBroadException
            try:
                DIVISION = defs.FIPS_DIVN[input1]
                if not DIVISION:
                    DIVISION = 'areas'
            except:
                DIVISION = 'municipalities'
        else:
            # noinspection PyBroadException
            try:
                DIVISION = defs.FIPS_DIVN[input1]
                if not DIVISION:
                    DIVISION = 'áreas'
            except:
                DIVISION = 'municipios'
    else:
        DIVISION = 'areas'
    return DIVISION


def get_event(input1):
    event = None
    args = parse_arguments()
    # noinspection PyBroadException
    try:
        if args.lang == 'SP':
            event = defs.SAME__EEE__SP[input1]
        else:
            event = defs.SAME__EEE[input1]
    except:
        if input1[2:] in 'WAESTMN':
            event = ' '.join(['Unknown', defs.SAME_UEEE[input1[2:]]])
    return event


def get_indicator(input1):
    indicator = None
    # noinspection PyBroadException
    try:
        if input1[2:] in 'WAESTMNR':
            indicator = input1[2:]
    except:
        pass
    return indicator


def printf(output=''):
    output = output.lstrip(' ')
    output = ' '.join(output.split())
    sys.stdout.write(''.join([output, ' ']))


def alert_end(JJJHHMM, TTTT):
    alertstart = alert_start(JJJHHMM)
    delta = datetime.timedelta(hours=int(TTTT[:2]), minutes=int(TTTT[2:]))
    return alertstart + delta


def alert_length(TTTT):
    delta = datetime.timedelta(hours=int(TTTT[:2]), minutes=int(TTTT[2:]))
    return delta.seconds


def get_location(STATION=None, TYPE=None):
    location = ''
    if TYPE == 'NWS':
        # noinspection PyBroadException
        try:
            # CHANGED WITHOUT TESTING
            location = defs.ICAO_LIST[STATION]
        except:
            pass
    return location


def check_watch(watch_list, PSSCCC_list, event_list, EEE):
    if not watch_list:
        watch_list = PSSCCC_list
    if not event_list:
        event_list = [EEE]
    w, p = [], []
    w += [item[1:] for item in watch_list]
    p += [item[1:] for item in PSSCCC_list]
    if (set(w) & set(p)) and EEE in event_list:
        return True
    else:
        return False


def kwdict(**kwargs):
    return kwargs


def format_message(command, ORG='WXR', EEE='RWT', PSSCCC=None, TTTT='0030', JJJHHMM='0010000', STATION=None, TYPE=None,
                   LLLLLLLL=None, COUNTRY='US', LANG='EN', MESSAGE=None, **kwargs):
    if PSSCCC is None:
        PSSCCC = []
    return command.format(ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION, TYPE=TYPE, LLLLLLLL=LLLLLLLL,
                          COUNTRY=COUNTRY, LANG=LANG, event=get_event(EEE), type=get_indicator(EEE),
                          end=fn_dt(alert_end(JJJHHMM, TTTT)), start=fn_dt(alert_start(JJJHHMM)),
                          organization=defs.SAME__ORG[LANG][ORG]['NAME'][COUNTRY], PSSCCC='-'.join(PSSCCC),
                          location=get_location(STATION, TYPE), date=fn_dt(datetime.datetime.now(), '%c'),
                          length=get_length(TTTT), seconds=alert_length(TTTT), MESSAGE=MESSAGE, **kwargs)


def readable_message(ORG='WXR', EEE='RWT', PSSCCC=None, TTTT='0030', JJJHHMM='0010000', STATION=None, TYPE=None,
                     LLLLLLLL=None, COUNTRY='US', LANG='EN'):
    if PSSCCC is None:
        PSSCCC = []
    import re
    location = get_location(STATION, TYPE)
    MSG = [format_message(defs.MSG__TEXT[LANG]['MSG1'], ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION,
                          TYPE=TYPE, COUNTRY=COUNTRY, LANG=LANG,
                          article=defs.MSG__TEXT[LANG][defs.SAME__ORG[LANG][ORG]['ARTICLE'][COUNTRY]].title(),
                          has=defs.MSG__TEXT[LANG]['HAS'] if not defs.SAME__ORG[LANG][ORG]['PLURAL'] else
                          defs.MSG__TEXT[LANG]['HAVE'],
                          preposition=defs.MSG__TEXT[LANG]['IN'] if location != '' else '')]
    current_state = None
    for idx, item in enumerate(PSSCCC):
        county, state = county_decode(item, COUNTRY, LANG)
        if current_state != state:
            DIVISION = get_division(PSSCCC[idx][1:3], COUNTRY, LANG)
            output = defs.MSG__TEXT[LANG]['MSG2'].format(conjunction='' if idx == 0 else defs.MSG__TEXT[LANG]['AND'],
                                                         state=state, division=DIVISION)
            MSG += [''.join(output)]
            current_state = state
        MSG += [defs.MSG__TEXT[LANG]['MSG3'].format(
            county=county if county != state else defs.MSG__TEXT[LANG]['ALL'].upper(),
            punc=',' if idx != len(PSSCCC) - 1 else '.')]
    MSG += [defs.MSG__TEXT[LANG]['MSG4']]
    MSG += [''.join(['(', LLLLLLLL, ')'])]
    final_str = ''.join(MSG)
    printf(final_str)
    return final_str


def clean_msg(same):
    valid_chars = ''.join([string.ascii_uppercase, string.digits, '+-/*'])
    same = same.upper()  # Uppercase
    msgidx = same.find('ZCZC')
    if msgidx != -1:
        same = same[msgidx:]  # Left Offset
    same = ''.join(same.split())  # Remove whitespace
    same = ''.join(filter(lambda x: x in valid_chars, same))  # Valid ASCII codes only
    slen = len(same) - 1
    if same[slen] != '-':
        ridx = same.rfind('-')
        offset = slen - ridx
        if offset <= 8:
            same = ''.join([same.ljust(slen + (8 - offset) + 1, '?'), '-'])  # Add final dash and/or pad location field

    return same


def same_decode(same, lang, same_watch=None, event_watch=None, text=True, call=None, command=None, jsonfile=None):
    args = parse_arguments()
    global file, stream, recorded_frames, same1, message1
    while len(same):
        # noinspection PyUnusedLocal
        tail = same
        # noinspection PyBroadException
        try:
            same = clean_msg(same)
        except:
            return
        msgidx = same.find('ZCZC')
        endidx = same.find('NNNN')
        if msgidx != -1 and (endidx == -1 or endidx > msgidx):
            # New message
            logging.debug('-' * 30)
            logging.debug(' '.join(['    Identifer found >', 'ZCZC']))
            # noinspection PyUnusedLocal
            S1, S2 = None, None
            # noinspection PyBroadException
            try:
                S1, S2 = same[msgidx:].split('+', 1)
            except:
                format_error()
                return
            # noinspection PyBroadException
            try:
                ZCZC, ORG, EEE, PSSCCC = S1.split('-', 3)
            except:
                format_error()
                return
            logging.debug(' '.join(['   Originator found >', ORG]))
            logging.debug(' '.join(['   Event Code found >', EEE]))
            # noinspection PyBroadException
            try:
                PSSCCC_list = PSSCCC.split('-')
            except:
                format_error()
            # noinspection PyBroadException
            try:
                TTTT, JJJHHMM, LLLLLLLL, tail = S2.split('-', 3)
            except:
                format_error()
                return
            logging.debug(' '.join(['   Purge Time found >', TTTT]))
            logging.debug(' '.join(['    Date Code found >', JJJHHMM]))
            logging.debug(' '.join(['Location Code found >', LLLLLLLL]))
            # noinspection PyBroadException
            try:
                STATION, TYPE = LLLLLLLL.split('/')
            except ValueError:
                # Station doesn't have to have a /
                STATION = LLLLLLLL
                TYPE = None
                pass
            except:
                STATION, TYPE = None, None
                format_error()
            # noinspection PyUnboundLocalVariable
            logging.debug(' '.join(['   SAME Codes found >', str(len(PSSCCC_list))]))
            US_bad_list = []
            CA_bad_list = []
            MX_bad_list = []
            for code in PSSCCC_list:
                try:
                    # noinspection PyUnusedLocal
                    county = defs.US_SAME_CODE[code[1:]]
                except KeyError:
                    US_bad_list.append(code)
                try:
                    # noinspection PyUnusedLocal
                    county = defs.CA_SAME_CODE[code[1:]]
                except KeyError:
                    CA_bad_list.append(code)
                try:
                    # noinspection PyUnusedLocal
                    county = defs.MX_SAME_CODE[code[1:]]
                except KeyError:
                    MX_bad_list.append(code)
            if len(US_bad_list) < len(CA_bad_list) and len(US_bad_list) < len(MX_bad_list):
                COUNTRY = 'US'
            if len(US_bad_list) > len(CA_bad_list) and len(CA_bad_list) < len(MX_bad_list):
                COUNTRY = 'CA'
            if len(US_bad_list) > len(MX_bad_list) and len(CA_bad_list) > len(MX_bad_list):
                COUNTRY = 'MX'
            if len(US_bad_list) == len(MX_bad_list) and len(US_bad_list) == len(CA_bad_list):
                if type == 'CA':
                    COUNTRY = 'CA'
                elif type == 'MX':
                    COUNTRY = 'MX'
                else:
                    COUNTRY = 'US'
            # noinspection PyUnboundLocalVariable
            if COUNTRY == 'CA':
                bad_list = CA_bad_list
            elif COUNTRY == 'MX':
                bad_list = MX_bad_list
            elif COUNTRY == 'US':
                bad_list = US_bad_list
            # noinspection PyUnboundLocalVariable
            logging.debug(' '.join(['Invalid Codes found >', str(len(bad_list)), ', '.join(bad_list)]))
            logging.debug(' '.join(['            Country >', COUNTRY]))
            logging.debug('-' * 30)
            for code in bad_list:
                PSSCCC_list.remove(code)
            PSSCCC_list.sort()
            if check_watch(same_watch, PSSCCC_list, event_watch, EEE):
                if text:
                    MESSAGE = readable_message(ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE, LLLLLLLL, COUNTRY,
                                               lang)
                    message1 = MESSAGE
                    same1 = str(same)
                    if args.record:
                        """and not args.source == 'rtl' will be removed once a way to record the SDR stream is found"""
                        if not is_recording and not args.source == 'file':
                            if args.source == 'rtl':
                                sys.stdout.write('rtl\n')
                            else:
                                # Start recording

                                sys.stdout.write('Recording started. ')
                                set_is_recording(1)
                                set_FILE_NAME(EEE, args.record)
                                sys.stdout.write(FILE_NAME_PATH + FILE_NAME)
                                sys.stdout.write('\n')
                                stream = sd.InputStream(callback=callback, channels=CHANNELS, samplerate=SAMPLE_RATE)
                                stream.start()
                else:
                    MESSAGE = None
                    same1 = str(same)
                    if args.record:
                        """and not args.source == 'rtl' will be removed once a way to record the SDR stream is found"""
                        if not is_recording and not args.source == 'file':
                            if args.source == 'rtl':
                                sys.stdout.write('rtl\n')
                            else:
                                # Start recording
                                sys.stdout.write('Recording started. ')
                                set_is_recording(1)
                                set_FILE_NAME(EEE, args.record)
                                sys.stdout.write(FILE_NAME_PATH + FILE_NAME)
                                sys.stdout.write('\n')
                                stream = sd.InputStream(callback=callback, channels=CHANNELS, samplerate=SAMPLE_RATE)
                                stream.start()
                if jsonfile:
                    try:
                        import json
                        data = kwdict(ORG=ORG, EEE=EEE, TTTT=TTTT, JJJHHMM=JJJHHMM, STATION=STATION, TYPE=TYPE,
                                      LLLLLLLL=LLLLLLLL, COUNTRY=COUNTRY, LANG=lang, event=get_event(EEE),
                                      type=get_indicator(EEE), end=fn_dt(alert_end(JJJHHMM, TTTT)),
                                      start=fn_dt(alert_start(JJJHHMM)),
                                      organization=defs.SAME__ORG[lang][ORG]['NAME'][COUNTRY], PSSCCC=PSSCCC,
                                      PSSCCC_list=PSSCCC_list, location=get_location(STATION, TYPE),
                                      date=fn_dt(datetime.datetime.now(), '%c'), length=get_length(TTTT),
                                      seconds=alert_length(TTTT), MESSAGE=MESSAGE)
                        with open(jsonfile, 'w') as outfile:
                            json.dump(data, outfile)
                    except Exception as detail:
                        logging.error(detail)
                        return
                if command:
                    if call:
                        l_cmd = []
                        for cmd in command:
                            l_cmd.append(
                                format_message(cmd, ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE, LLLLLLLL,
                                               COUNTRY, lang, MESSAGE))
                        try:
                            subprocess.call([call] + l_cmd)
                        except Exception as detail:
                            logging.error(detail)
                            return
                        pass
                    else:
                        f_cmd = format_message(command, ORG, EEE, PSSCCC_list, TTTT, JJJHHMM, STATION, TYPE,
                                               LLLLLLLL, COUNTRY, lang, MESSAGE)
                        #printf(f_cmd)
        else:
            if endidx == -1:
                logging.warning('Valid identifer not found.')
                return
            else:
                """and not args.source == 'rtl' will be removed once a way to record the SDR stream is found"""
                if args.record and is_recording and not args.source == 'rtl':
                    # RECORDING STOP
                    stream.stop()
                    stream.close()
                    recorded_frames = np.concatenate(recorded_frames)
                    # noinspection PyBroadException
                    try:
                        sf.write(FILE_NAME_PATH + FILE_NAME, recorded_frames, SAMPLE_RATE, 'PCM_24')
                        sys.stdout.write('Recording stopped. File saved as ' + FILE_NAME_PATH + FILE_NAME + '\n')
                        set_is_recording(0)
                        recorded_frames = []
                        try:
                            if args.transcribe and not args.source == 'file':
                                # noinspection PyUnboundLocalVariable
                                background_process = multiprocessing.Process(name='background_process',
                                                                             target=transcribe_alert_faster,
                                                                             args=(args.transcribe,
                                                                                   args.transcription_model, same1,
                                                                                   FILE_NAME_PATH, FILE_NAME, message1,
                                                                                   args.lang,
                                                                                   args.transcription_compute,
                                                                                   args.transcription_beam_size,
                                                                                   args.transcription_device))
                                background_process.daemon = True
                                background_process.start()
                        except Exception as e:
                            sys.stdout.write('Error: ' + str(e) + '\n')
                    except Exception as e:
                        sys.stdout.write(
                            'Error. Recording could not be saved. Please check your path and make sure it is '
                            'correct and you have access. \n ERROR DETAILS: ' + str(e) + '\n')
                        set_is_recording(0)
                logging.debug(' '.join(['End of Message found >', 'NNNN', str(msgidx)]))
                tail = same[msgidx:+len('NNNN')]
        # Move ahead and look for more
        same = tail


def parse_arguments():
    parser = argparse.ArgumentParser(description=defs.DESCRIPTION, prog=defs.PROGRAM, fromfile_prefix_chars='@')
    parser.add_argument('--msg', help='message to decode')
    parser.add_argument('--same', nargs='*', help='filter by SAME code')
    parser.add_argument('--event', nargs='*', help='filter by event code')
    parser.add_argument('--lang', default='EN', help='set language')
    parser.add_argument('--loglevel', default=40, type=int, choices=[10, 20, 30, 40, 50], help='set log level')
    parser.add_argument('--text', dest='text', action='store_true', help='output readable message')
    parser.add_argument('--no-text', dest='text', action='store_false', help='disable readable message')
    parser.add_argument('--version', action='version', version=' '.join([defs.PROGRAM, defs.VERSION]),
                        help='show version infomation and exit')
    parser.add_argument('--call', help='call external command')
    parser.add_argument('--command', nargs='*', help='command message')
    parser.add_argument('--json', help='write to json file')
    parser.add_argument('--source', default='soundcard', choices=['rtl', 'soundcard', 'file'], help='source program')
    # parser.add_argument('--script', help='script program')
    parser.add_argument('--frequency', nargs='*', help='Set the RTL_FM frequency')
    parser.add_argument('--ppm', nargs='*', help='Set the RTL_FM PPM')
    parser.add_argument('--record', nargs='*',
                        help='Record on valid SAME tone. Set recording location. ex. "C:\\Recordings". NOTE: Paths '
                             'can be either absolute or relative. RECORDINGS CURRENTLY DO NOT WORK WITH RTL AND DO NOT '
                             'WORK WITH FILE')
    parser.add_argument('--transcribe', nargs='*', help='Creates a text file with a transcription of the alert '
                                                        'message. Set transcription location. ex. "C:\\Recordings". '
                                                        'NOTE: Paths can be either absolute or relative. '
                                                        'ADDITIONAL NOTE: Recording must be enabled for transcription '
                                                        'to work. TRANSCRIPTIONS CURRENTLY DO NOT WORK WITH RTL')
    parser.add_argument('--transcription_model', default='medium', choices=['small', 'medium', 'large'],
                        help='Selects the model used for transcription (the larger the model,'
                             'the more resources/time '
                             'it takes)')
    parser.add_argument('--transcription_device', default='cpu', choices=['cpu', 'cuda', 'auto'],
                        help='Sets the device used for computation of the transcrtiption model (CURRENTLY, ONLY CPU '
                             'WORKS)')
    parser.add_argument('--transcription_compute', default='float32', choices=['int8', 'int8_float16', 'int16',
                                                                               'float16', 'float32'],
                        help='Choose the compute method for transcription. NOTE: only certain computation choices '
                             'will work with certain devices. ')
    parser.add_argument('--transcription_beam_size', type=int, default=5, help='Choose the beam size for '
                                                                               'transcription. NOTE: The higher the '
                                                                               'beam size, the more accurate the '
                                                                               'transcription will be, but the more '
                                                                               'time and resources it will take. ')
    parser.add_argument('--monitor', action='store_true', help='Enables monitoring. Choose whether you want the '
                                                               'selected source device output to be played through '
                                                               'the default output device')
    parser.add_argument('--skip_dependency', action='store_true', help='Skips dependency checking (MUST USE IF OFFLINE)'
                        )
    #    parser.add_argument('--sourceselect', help='Allows you to select microphone input on startup')
    parser.add_argument('--audiofile', help='Set audio file location when using source type "FILE" '
                                            'ex. "C:\\Recordings". NOTE: Paths can be either absolute or '
                                            'relative.')  # FOR DECODING AUDIO FILE
    #    parser.add_argument() FOR ALARM WINDOW OPTIONS
    parser.set_defaults(text=True)
    args, unknown = parser.parse_known_args()
    return args


def main():
    args = parse_arguments()
    args.lang = args.lang.upper()
    # try:
    #     subprocess.check_output('multimon-ng -a EAS')
    # except Exception as e:
    #     sys.stdout.write(str(e) + '\n')
    #     time.sleep(5)
    #     os_clear()
    #     os.execv(sys.executable, ['python'] + sys.argv)
    logging.basicConfig(level=args.loglevel, format='%(levelname)s: %(message)s')
    if args.msg:
        same_decode(args.msg, args.lang, same_watch=args.same, event_watch=args.event, text=args.text, call=args.call,
                    command=args.command, jsonfile=args.json)
    elif args.source:
        if args.source == 'rtl':
            try:
                rtl_fm_cmd = ['rtl_fm', '-f', str(args.frequency[0]) + 'M', '-M', 'fm', '-s', '22050', '-E', 'dc', '-p',
                              str(args.ppm[0]), '-']
                multimon_ng_cmd = ['multimon-ng', '-t', 'raw', '-a', 'EAS', '-']
                sox_cmd = ['C:\\Program Files (x86)\\sox-14-4-2\\sox.exe', '-V1', '-b', '16',
                           '-c', '1', '-e', 'signed-integer', '-r', '22050', '-t', 'raw', '-',
                           '-t', 'waveaudio', 'default']
                rtl_fm_process = subprocess.Popen(rtl_fm_cmd, stdout=subprocess.PIPE, shell=True)
                multimon_ng_process = subprocess.Popen(multimon_ng_cmd, stdin=rtl_fm_process.stdout,
                                                       stdout=subprocess.PIPE, shell=True)

                # NEEDS FIX
                # if args.monitor:
                    # noinspection PyUnusedLocal
                #     sox_process = subprocess.Popen(sox_cmd, stdin=rtl_fm_process.stdout)

                source_process = multimon_ng_process
            except Exception as detail:
                logging.error(detail)
                return
        elif args.source == 'soundcard':
            # sys.stdout.write('Soundcard\n')
            try:
                multimon_ng_process = subprocess.Popen('multimon-ng -a EAS', stdout=subprocess.PIPE, shell=True)
                source_process = multimon_ng_process
                if args.monitor:
                    sys.stdout.write('MONITORING ENABLED\n')
                    subprocess.Popen(['python', 'wire.py'])
            except Exception as detail:
                logging.error(detail)
                return
        elif args.source == 'file':  # FIX
            try:
                global FILE_NAME_PATH, FILE_NAME
                FILE_NAME_PATH, FILE_NAME = os.path.split(os.path.abspath(args.audiofile))
                # sys.stdout.write(FILE_NAME_PATH + '\n')
                # sys.stdout.write(FILE_NAME + '\n')
                sox_process = subprocess.Popen('"C:\\Program Files (x86)\\sox-14-4-2\\sox.exe" -V1 -t wav "' +
                                               os.path.abspath(args.audiofile) + '" -e signed-integer -b 16 -c 1 -r '
                                                                                 '22050 -t raw "process.raw"',
                                               stdout=subprocess.PIPE, shell=True)
                sox_process.communicate()
                multimon_ng_process = subprocess.Popen('multimon-ng -a EAS -t raw "process.raw"', stdout=subprocess.PIPE
                                                       , shell=True)
                while multimon_ng_process.poll() is None:
                    line = multimon_ng_process.stdout.readline()
                    if line:
                        line1 = line.decode('ascii')
                        logging.debug(line1)
                        same_decode(line1, args.lang, same_watch=args.same, event_watch=args.event, text=args.text,
                                    call=args.call, command=args.command, jsonfile=args.json)
                # noinspection PyUnboundLocalVariable
                # same1 = 'TEST'
                # message1 = 'TEST'
                global same1, message1
                # sys.stdout.write(str(same1) + '\n')
                # sys.stdout.write(str(message1) + '\n')
                background_process = multiprocessing.Process(name='background_process',
                                                             target=transcribe_alert_faster,
                                                             args=(args.transcribe,
                                                                   args.transcription_model, str(same1),
                                                                   FILE_NAME_PATH, FILE_NAME, str(message1),
                                                                   args.lang,
                                                                   args.transcription_compute,
                                                                   args.transcription_beam_size,
                                                                   args.transcription_device))
                background_process.daemon = True
                background_process.start()
                background_process.join()
                # REMOVE PROCESS FILE
                os.remove(os.path.join(os.path.abspath(''), 'process.raw'))
                input("Please press enter to close the program...")
                exit()
            except Exception as detail:
                logging.error(detail)
                return
        else:
            sys.stdout.write('ERROR' + '\n')
            input("Please press enter to close the program...")
            exit()
        while True:
            line = source_process.stdout.readline()
            if line:
                line1 = line.decode('ascii')
                logging.debug(line1)
                same_decode(line1, args.lang, same_watch=args.same, event_watch=args.event, text=args.text,
                            call=args.call, command=args.command, jsonfile=args.json)
    else:
        while True:
            for line in sys.stdin:
                logging.debug(line)
                same_decode(line, args.lang, same_watch=args.same, event_watch=args.event, text=args.text,
                            call=args.call, command=args.command, jsonfile=args.json)


if __name__ == "__main__":
    # global RESTART_QUEUE
    args = parse_arguments()
    try:
        if not args.skip_dependency:
            os.system("title " + "dsame3 Dependency Checker")
            # if platform.system() == 'Linux':
            #     os.system('sudo apt install xterm')
            if platform.system() == 'MacOS':
                os.system('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install'
                          '.sh)"')
            dependency_check_model('small')
            dependency_check_model('medium')
            dependency_check_model('large-v2')
            dependency_check_model('small.en')
            dependency_check_model('medium.en')
            dependency_check_multimon()
            dependency_check_ffmpeg()
            dependency_check_rtl()
            #os_clear()
        if RESTART_QUEUE:
            # NEED TO FIX AND MAKE PRETTY
            input("A dependency has been installed that requires a restart of the program. Please press enter to "
                  "close the program...")
            exit()
        else:
            os.system("title " + "dsame3")
            main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        sys.stdout.write('Error: ' + str(e) + '\n')
        input("Please press enter to close the program...")
