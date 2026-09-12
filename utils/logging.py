import logging
import os
import sys
import threading
import traceback
from io import StringIO

log_stream = StringIO()

def _log_file_path():
    """Persistent log location that survives even if the process crashes."""
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    log_dir = os.path.join(base, 'Ascendara', 'InstallerLogs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'installer.log')

def setup_logging():
    # Create formatters and handlers
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Stream handler for console output (no-op when built as a windowed
    # exe, since sys.stdout is None there, but harmless to keep for
    # `python app.py` runs)
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # StringIO handler for the in-app log window
    string_handler = logging.StreamHandler(log_stream)
    string_handler.setFormatter(formatter)
    root_logger.addHandler(string_handler)

    # File handler so logs persist to disk even if the process crashes or
    # is killed, instead of only living in memory
    try:
        file_handler = logging.FileHandler(_log_file_path(), encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logging.info(f"Logging to file: {_log_file_path()}")
    except Exception as e:
        logging.warning(f"Could not set up file logging: {e}")

    # Catch any otherwise-uncaught exception on the main thread and log it
    # before the process dies, so crashes leave a trace on disk.
    def _log_unhandled_exception(exc_type, exc_value, exc_tb):
        logging.critical(
            "Unhandled exception, application is crashing:\n" +
            ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _log_unhandled_exception

    # Same, but for background threads (installer + animation loop run in
    # threads, and exceptions there are otherwise silently swallowed)
    def _log_thread_exception(args):
        logging.critical(
            f"Unhandled exception in thread {args.thread.name}:\n" +
            ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )
    threading.excepthook = _log_thread_exception