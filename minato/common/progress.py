from __future__ import annotations

import os
import sys
import time
from collections.abc import Sized
from typing import Any, Callable, Generic, Iterable, Iterator, TextIO, TypeVar, cast

T = TypeVar("T")
Self = TypeVar("Self", bound="Progress")

DISABLE_PROGRESSBAR = os.environ.get("MINATO_DISABLE_PROGRESSBAR", "0").lower() in ("1", "true")


def _dummy_iterator() -> Iterator[int]:
    iterations = 0
    while True:
        yield iterations
        iterations += 1


def _default_sizeof_formatter(size: int | float) -> str:
    if size % 1 < 1.0e-1:
        size = int(size)
    if isinstance(size, int):
        return str(size)
    else:
        return f"{size:.2f}"


class EMA:
    def __init__(self, alpha: float = 0.3):
        self._alpha = alpha
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    def update(self, value: float) -> None:
        self._value = self._alpha * value + (1.0 - self._alpha) * self._value

    def reset(self) -> None:
        self._value = 0.0


class Progress(Generic[T]):
    def __init__(
        self,
        total_or_iterable: int | Iterable[T] | None,
        desc: str | None = None,
        unit: str = "it",
        output: TextIO = sys.stderr,
        maxwidth: int | None = None,
        partchars: str = " ▏▎▍▌▋▊▉█",
        sizeof_formatter: Callable[[int | float], str] = _default_sizeof_formatter,
        disable: bool = False,
    ) -> None:
        total_or_iterable = total_or_iterable or cast(Iterator[T], _dummy_iterator())
        self._iterable = (
            cast(Iterator[T], range(total_or_iterable)) if isinstance(total_or_iterable, int) else total_or_iterable
        )
        self._total = len(self._iterable) if isinstance(self._iterable, Sized) else None
        self._desc = desc
        self._unit = unit
        self._output = output
        self._maxwidth = maxwidth
        self._partchars = partchars
        self._sizeof_formatter = sizeof_formatter
        self._disable = disable or DISABLE_PROGRESSBAR

        self._postfixes: dict[str, Any] = {}

        self._iterations = 0
        self._start_time = time.time()
        self._last_time = self._start_time
        self._interval_ema = EMA()

    @staticmethod
    def _format_time(seconds: float) -> str:
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{int(h):d}:{int(m):02d}:{int(s):02d}"
        else:
            return f"{int(m):02d}:{int(s):02d}"

    def _get_maxwidth(self) -> int:
        try:
            terminal_width, _ = os.get_terminal_size()
        except OSError:
            terminal_width = 80
        if self._maxwidth:
            return min(terminal_width, self._maxwidth)
        else:
            return terminal_width

    def _get_bar(self, width: int, percentage: float) -> str:
        ratio = percentage / 100
        width = max(1, width)
        whole_width = int(ratio * width)
        part_width = int(len(self._partchars) * ((ratio * width) % 1))
        part_char = self._partchars[part_width]
        return f"{(self._partchars[-1] * whole_width + part_char)[:width]:{width}s}"

    def set_postfix(self, **postfixes: Any) -> None:
        self._postfixes = postfixes

    def show(self) -> None:
        if self._disable:
            return

        template = ""
        contents: dict[str, Any] = {}

        elapsed_time = time.time() - self._start_time
        average_iterations = 1.0 / self._interval_ema.value if self._interval_ema.value > 0.0 else 0.0

        contents["desc"] = self._desc
        contents["unit"] = self._unit
        contents["iterations"] = self._sizeof_formatter(self._iterations)
        contents["elapsed_time"] = self._format_time(elapsed_time)
        contents["average_iterations"] = self._sizeof_formatter(average_iterations)

        postfixes = [f"{key}={val}" for key, val in self._postfixes.items()]

        if self._desc:
            template = "{desc}: " + template
            contents["desc"] = self._desc

        if self._total is None:
            postfixes = [
                "{elapsed_time}",
                "{average_iterations}{unit}/s",
            ] + postfixes
            postfix_template = " ".join(postfixes)
            template = template + " {iterations}{unit} " + f"[{postfix_template}]"
        else:
            total_width = len(self._sizeof_formatter(self._total))
            percentage = 100 * self._iterations / self._total
            remaining_time = (self._total - self._iterations) / average_iterations if average_iterations > 0.0 else 0.0

            postfixes = [
                "{elapsed_time}<{remaining_time}",
                "{average_iterations}{unit}/s",
            ] + postfixes
            postfix_template = " ".join(postfixes)

            template = (
                template + "{percentage:5.1f}% |{bar}| {iterations:>{total_width}}/{total} " + f"[{postfix_template}]"
            )

            contents["total_width"] = total_width
            contents["percentage"] = percentage
            contents["bar"] = ""
            contents["total"] = self._sizeof_formatter(self._total)
            contents["remaining_time"] = self._format_time(remaining_time)

            barwidth = max(1, self._get_maxwidth() - len(template.format(**contents)))
            contents["bar"] = self._get_bar(barwidth, percentage)

        line = template.format(**contents)
        self._output.write(f"\x1b[?25l\x1b[2K\r{line}")
        self._output.flush()

    def update(self, iterations: int = 1) -> None:
        current_time = time.time()
        self._interval_ema.update(current_time - self._last_time)
        self._iterations += iterations
        self._last_time = current_time
        self.show()

    def __iter__(self) -> Iterator[T]:
        self._iterations = 0
        self._start_time = time.time()

        with self:
            for item in self._iterable:
                yield item
                self.update()

    def __enter__(self: Self) -> Self:
        self._iterations = 0
        self._start_time = time.time()
        self.show()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._output.write("\x1b[?25h\n")
        self._output.flush()
