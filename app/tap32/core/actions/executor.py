"""Wykonywanie akcji poza wątkiem GUI, z logowaniem błędów."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from .base import ActionBase, ActionContext

log = logging.getLogger("tap32.actions")

DoneCallback = Callable[[ActionBase, ActionContext, BaseException | None], None]


class ActionExecutor:
    """Pula wątków wykonująca akcje. Błąd akcji jest logowany i nie przerywa aplikacji."""

    def __init__(
        self,
        workers: int = 4,
        thread_init: Callable[[], None] | None = None,
        synchronous: bool = False,
    ) -> None:
        self._synchronous = synchronous
        self._pool: ThreadPoolExecutor | None = None
        if not synchronous:
            self._pool = ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="tap32-action", initializer=thread_init
            )

    def submit(
        self, action: ActionBase, ctx: ActionContext, on_done: DoneCallback | None = None
    ) -> Future[None] | None:
        if self._pool is None:
            self._run(action, ctx, on_done)
            return None
        return self._pool.submit(self._run, action, ctx, on_done)

    @staticmethod
    def _run(action: ActionBase, ctx: ActionContext, on_done: DoneCallback | None) -> None:
        error: BaseException | None = None
        try:
            action.execute(ctx)
        except Exception as exc:
            error = exc
            log.error("Akcja „%s” nie powiodła się: %s", action.summary(), exc)
        if on_done is not None:
            try:
                on_done(action, ctx, error)
            except Exception:
                log.exception("Błąd w obsłudze zakończenia akcji")

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
