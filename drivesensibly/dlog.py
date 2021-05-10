import logging
import sys

from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path


class DebugOnly(object):
    def filter(self, logRecord):
        return logRecord.levelno <= logging.DEBUG

class WarningOnly(object):
    def filter(self, logRecord):
        return logRecord.levelno <= logging.WARNING

class SingleLevel(object):
    def __init__(self, level):
        self.level = level

    def filter(self, logRecord):
        return logRecord.levelno == self.level

def setup_logging(loglevel):
    levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
    }

    # Set log file name.
    utc_time = datetime.now(tz=timezone.utc)
    hh = f"{utc_time.hour:02}"
    mm = f"{utc_time.minute:02}"
    ss = f"{utc_time.second:02}"
    timestamp = f"{date.today()}-{hh}{mm}{ss}"
    log_name = f"drive-sensibly-{timestamp}.log"
    log_path = Path(__file__).parents[1] / 'log' / log_name

    # Basic logging format.
    basic_format = '%(message)s'
    debug_format = '%(levelname)s:%(module)s:%(funcName)s:%(lineno)s: %(message)s'

    # Define handlers.
    debug = logging.StreamHandler()
    debug_formatter = logging.Formatter(debug_format)
    debug.setLevel(logging.DEBUG)
    debug.addFilter(DebugOnly())
    debug.setFormatter(debug_formatter)

    logfile = logging.FileHandler(log_path)
    logfile_formatter = logging.Formatter(basic_format)
    logfile.setLevel(logging.INFO)
    logfile.setFormatter(logfile_formatter)

    stdout = logging.StreamHandler(sys.stdout)
    stdout_formatter = logging.Formatter(basic_format)
    stdout.setLevel(logging.INFO)
    stdout.setFormatter(stdout_formatter)

    # stderr = logging.StreamHandler(sys.stderr)
    # stderr_formatter = logfile_formatter
    # stderr.setLevel(logging.INFO)
    # stderr.addFilter(WarningOnly())
    # stderr.setFormatter(stderr_formatter)

    # Intialize logging with basicConfg; This defines stderr output.
    logging.basicConfig(
        level=levels.get(loglevel),
        # format=basic_format,
        # handlers=[debug, logfile, stdout, stderr]
        handlers=[debug, logfile, stdout]
    )
    # logging.getLogger().handlers.clear()
    # for handler in [debug, logfile, stdout, stderr]:
    #     logging.getLogger().addHandler(handler)

    # Silence silly "file_cache" WARNING:
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
