"""Qt QThread and QRunnable worker utilities for non-blocking background execution."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Signals emitted by a background task worker."""

    started = pyqtSignal()
    progress = pyqtSignal(object)
    result = pyqtSignal(object)
    error = pyqtSignal(str, str)  # (error_message, traceback_str)
    finished = pyqtSignal()


class TaskWorker(QRunnable):
    """Generic QRunnable that executes a callable on the global QThreadPool."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        self.signals.started.emit()
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(res)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Background task error in %s: %s", getattr(self.fn, "__name__", "fn"), exc)
            self.signals.error.emit(str(exc), tb)
        finally:
            self.signals.finished.emit()


def run_in_background(
    fn: Callable[..., Any],
    *args: Any,
    on_result: Callable[[Any], None] | None = None,
    on_error: Callable[[str, str], None] | None = None,
    on_finished: Callable[[], None] | None = None,
    **kwargs: Any,
) -> TaskWorker:
    """Schedule a callable on the global QThreadPool and wire optional callbacks."""
    worker = TaskWorker(fn, *args, **kwargs)
    if on_result is not None:
        worker.signals.result.connect(on_result)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    if on_finished is not None:
        worker.signals.finished.connect(on_finished)
    QThreadPool.globalInstance().start(worker)
    return worker
