import ctypes
import logging
import sys
import traceback
from multiprocessing import freeze_support

from gui.dpi import make_process_dpi_aware
from util.crash import crash_report

__version__ = "1.0.0"

# Must happen before ANY Tk window is created — including the crash-handler's
# messagebox fallback further down — so it runs at import time, unconditionally.
make_process_dpi_aware()

logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(filename="history.log")
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

debug_logger = logging.getLogger("debugger")
debug_logger.setLevel(logging.DEBUG)
if not debug_logger.handlers:
    fh = logging.FileHandler("debugger.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "[%(asctime)s][%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
debug_logger.addHandler(fh)


def _show_error(title: str, message: str) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()


def _main() -> None:
    freeze_support()

    import pydivert

    from gui.main_window import MainWindow
    from menu.menu import Menu
    from network.connectionlog import ConnectionLogger
    from util.hotkeys import register_hotkeys

    if not ctypes.windll.shell32.IsUserAnAdmin():
        logger.info("Started without admin")
        _show_error("G-Lock", "Please restart G-Lock as administrator.")
        sys.exit()

    if not pydivert.WinDivert.is_registered():
        pydivert.WinDivert.register()

    # The console is only kept around as a last-resort fallback for
    # tracebacks that occur before the crash handler below can show a
    # messagebox (e.g. Tk itself failing to initialise) — hide it once we've
    # gotten this far, so the app looks and behaves like a normal GUI program.
    console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if console_hwnd:
        ctypes.windll.user32.ShowWindow(console_hwnd, 0)  # SW_HIDE

    # Runs for the whole lifetime of the app, independent of whichever
    # session filter (if any) is active — so "who connected and when" can be
    # investigated later even if you were just sitting in "Open" the whole
    # time a cheater got in.
    ConnectionLogger().start()

    register_hotkeys(Menu)
    window = MainWindow(Menu, version=__version__)
    window.run()


if __name__ == "__main__":
    try:
        _main()
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except Exception as e:
        # Last-resort safety net: crash_report() + a traceback on the
        # (possibly hidden) console are backed up by a visible messagebox,
        # since a GUI build has no guaranteed console left for the user to
        # read a paused traceback from.
        report_path = crash_report(e, "G-Lock crashed")
        traceback.print_exc()
        _show_error(
            "G-Lock crashed",
            f"G-Lock encountered a fatal error and must close.\n\n{e}\n\n"
            f"A crash report was saved to:\n{report_path}",
        )
        raise
