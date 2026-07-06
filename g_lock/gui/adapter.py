from __future__ import annotations

import queue
import threading
import tkinter as tk
from abc import ABC, abstractmethod
from typing import Callable, TypeVar

from gui import dialogs

T = TypeVar("T")

MainQueue = queue.Queue[Callable[[], None]]


class UIAdapter(ABC):
    """
    The presentation boundary `Menu`'s business-logic methods talk to instead
    of calling `questionary`/`print`/`tqdm` directly. Business-logic methods
    are expected to run on a background worker thread (never the GUI main
    thread) so these calls can block that worker thread while the actual
    widgets are shown on the main thread.
    """

    @abstractmethod
    def confirm(self, title: str, message: str) -> bool: ...

    @abstractmethod
    def select_multiple(self, title: str, message: str, choices: list[str]) -> list[str]: ...

    @abstractmethod
    def run_with_progress(
        self,
        title: str,
        total: int,
        work: Callable[[Callable[[int], None], threading.Event], T],
    ) -> T: ...


class TkUIAdapter(UIAdapter):
    def __init__(self, root: tk.Tk, main_queue: MainQueue):
        self.root = root
        self.main_queue = main_queue

    def _run_on_main_and_wait(self, build: Callable[[], T]) -> T:
        """
        Enqueues `build` to run on the Tk main thread (via MainWindow's task
        pump) and blocks the CALLING thread until it has run and produced a
        result. Must only be called from a worker thread — if called from the
        main thread itself, the pump that would service `main_queue` is the
        very thread now blocked on `response.get()`, which deadlocks.
        """
        response: "queue.Queue[T]" = queue.Queue(maxsize=1)

        def _task() -> None:
            response.put(build())

        self.main_queue.put(_task)
        return response.get()

    def confirm(self, title: str, message: str) -> bool:
        return self._run_on_main_and_wait(
            lambda: dialogs.show_confirm(self.root, title, message)
        )

    def select_multiple(self, title: str, message: str, choices: list[str]) -> list[str]:
        return self._run_on_main_and_wait(
            lambda: dialogs.show_multiselect(self.root, title, message, choices)
        )

    def run_with_progress(
        self,
        title: str,
        total: int,
        work: Callable[[Callable[[int], None], threading.Event], T],
    ) -> T:
        cancel_event = threading.Event()
        dialog_box: list[dialogs.ProgressDialog] = []
        created = threading.Event()

        def _open() -> None:
            dialog_box.append(dialogs.ProgressDialog(self.root, title, total, cancel_event))
            created.set()

        self.main_queue.put(_open)
        created.wait()
        dialog = dialog_box[0]

        try:
            return work(dialog.report, cancel_event)
        finally:
            dialog.close()
