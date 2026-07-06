"""
This file contains a custom logger with different print levels and specific formatting.
It also contains a progress bar function that can be used to show progress of a loop.
The decorator_provide_time_information can be used to wrap a function and provide time
    together with a starting and finished message, that works congruently with the logger.

Example usage:
    logger = CustomLogger("test_logger", "logs")
    logger.info("This is an info message", print_level=3)
    logger.starting("This is a starting message", print_level=3)
    logger.finished("This is a finished message", print_level=3)

Created by Jelle Bonthuis on 2025-03-24
"""

import atexit
import cProfile
import io
import pstats
import re
import tracemalloc
from collections import defaultdict
from dataclasses import fields, is_dataclass
from datetime import datetime
from functools import partial, wraps
from inspect import getsourcelines, stack
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    Filter,
    Formatter,
    Logger,
    StreamHandler,
    addLevelName,
    getLogger,
)
from os import getpid
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Optional, cast

import line_profiler
import pandas as pd
import psutil
from memory_profiler import memory_usage

# todo add function nesting for color adjustments (so starting and finished will
#  have different colors depending on what level they are called from)

DEFAULT_DECORATOR_PRINT_LEVEL = 4
DEFAULT_DECORATOR_TIME_DECIMALS = 4
DEFAULT_BACKUP_LOGGER_PRINT_LEVEL = 3


def parse_log_file(log_path: str | Path) -> pd.DataFrame:  # noqa: C901
    """Generated: validation needed.

    Description:
        Parse a log file written by :class:`CustomLogger` and return a DataFrame
        pairing each STARTING entry with its corresponding FINISHED entry.

    Args:
        log_path (str | Path): Path to the ``.log`` file to parse.

    Returns:
        pd.DataFrame: DataFrame with columns ``function``, ``file``, ``start_time``,
            ``end_time``, ``duration``, ``lineno``, and ``calls``.
    """
    pattern_start = re.compile(r"STARTING - Starting: (.*?) \((.*?):(\d+)\)")
    pattern_finish = re.compile(
        r"FINISHED - Finished: (.*?) in: ([\d.]+) seconds \((.*?):(\d+)\)"
    )

    calls = []
    call_counts = defaultdict(int)

    with open(log_path, "r") as f:
        for line in f:
            timestamp_str = line.split(" - ")[0].strip()
            timestamp_str = timestamp_str[
                : timestamp_str.rfind(",")
            ].strip()  # Extract timestamp part
            try:
                timestamp = datetime.strptime(
                    timestamp_str,
                    "%Y-%m-%d %H:%M:%S",
                )
            except ValueError:
                continue  # skip malformed lines

            if "STARTING - Starting" in line:
                match = pattern_start.search(line)
                if match:
                    func, file, lineno = match.groups()
                    calls.append(
                        {
                            "function": func,
                            "file": file,
                            "lineno": int(lineno),
                            "timestamp": timestamp,
                            "type": "start",
                        }
                    )
                    call_counts[func] += 1
            elif "FINISHED - Finished" in line:
                match = pattern_finish.search(line)
                if match:
                    func, duration, file, lineno = match.groups()
                    calls.append(
                        {
                            "function": func,
                            "file": file,
                            "lineno": int(lineno),
                            "timestamp": timestamp,
                            "type": "end",
                            "duration": float(duration),
                        }
                    )

    # Combine start and end pairs
    stack = []
    data = []
    for call in calls:
        if call["type"] == "start":
            stack.append(call)
        elif call["type"] == "end":
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]["function"] == call["function"]:
                    start_call = stack.pop(i)
                    data.append(
                        {
                            "function": call["function"],
                            "file": call["file"],
                            "start_time": start_call["timestamp"],
                            "end_time": call["timestamp"],
                            "duration": call["duration"],
                            "lineno": call["lineno"],
                            "calls": call_counts[call["function"]],
                        }
                    )
                    break
    df = pd.DataFrame(data)

    return df


class CustomLogger:
    VALID_LEVEL = 25
    HIGH_DETAIL_LEVEL = 24
    LOW_DETAIL_LEVEL = 23
    FINISHED_LEVEL = 22
    STARTING_LEVEL = 21

    def __init__(
        self,
        name: str,
        log_files_location: str | Path | None = None,
        print_level: int = 2,
        auto_parse: bool = False,
    ):
        """Generated: validation needed.

        Description:
            Initialise logger, attach console and file handlers, optionally
            register an atexit log-parser.

        Args:
            name (str): Logger name; also used as log filename stem.
            log_files_location (str | Path | None): Directory for log files.
                Defaults to ``utils/logs/`` when None.
            print_level (int): Maximum print-level passed through to console handler.
            auto_parse (bool): When True register :meth:`_run_log_parser` at exit.
        """
        if log_files_location is None:
            log_files_location_path = Path(__file__).resolve().parent / "logs"
        else:
            log_files_location_path = Path(log_files_location)

        self.logger: Logger = getLogger(name)
        self.name = name
        self.logger.setLevel(DEBUG)
        self.logger.propagate = False
        self.print_level = print_level
        self.filter = PrintLevelFilter(print_level)
        addLevelName(CustomLogger.VALID_LEVEL, "VALID")
        addLevelName(CustomLogger.FINISHED_LEVEL, "FINISHED")
        addLevelName(CustomLogger.STARTING_LEVEL, "STARTING")
        # Keep runtime compatibility for code using `custom_logger.logger.starting(...)`.
        logger_with_custom_levels = cast(Any, self.logger)
        logger_with_custom_levels.valid = self.valid
        logger_with_custom_levels.starting = self.starting
        logger_with_custom_levels.finished = self.finished
        # todo add extra ones that could be used
        console_handler = StreamHandler()
        console_handler.setLevel(DEBUG)
        console_handler.setFormatter(CustomFormatter())
        console_handler.addFilter(self.filter)
        self.logger.addHandler(console_handler)
        log_filename = name + ".log"
        log_files_location_path.mkdir(parents=True, exist_ok=True)
        log_file_path = log_files_location_path / log_filename

        file_handler = FileHandler(log_file_path, mode="w")
        file_handler.setFormatter(
            Formatter("%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
        )
        self.logger.addHandler(file_handler)
        self.log_file_path = log_file_path
        self.auto_parse = auto_parse

        if self.auto_parse:
            atexit.register(self._run_log_parser)

    def set_log_files_location(self, log_files_location: str, mode: str = "w") -> None:
        """Generated: validation needed.

        Description:
            Rebind the file handler to a new directory while preserving console logging.

        Args:
            log_files_location (str): New directory path for the log file.
            mode (str): File open mode passed to :class:`~logging.FileHandler`.
        """
        log_files_location_path = Path(log_files_location)
        log_files_location_path.mkdir(parents=True, exist_ok=True)

        log_filename = (
            self.log_file_path.name if hasattr(self, "log_file_path") else "run.log"
        )
        log_file_path = log_files_location_path / log_filename

        # Remove existing file handlers only; keep stream handlers and filters intact.
        handlers = list(self.logger.handlers)
        for handler in handlers:
            if isinstance(handler, FileHandler):
                self.logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass

        file_handler = FileHandler(log_file_path, mode=mode)
        file_handler.setFormatter(
            Formatter("%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
        )
        self.logger.addHandler(file_handler)
        self.log_file_path = log_file_path

    @staticmethod
    def fix_non_ascii_messages_decorator(func: Callable) -> Callable:
        """Generated: validation needed.

        Description:
            Decorator that sanitises log messages to cp1252-safe strings before
            passing them to the wrapped logging method.

        Args:
            func (Callable): Logging method to wrap.

        Returns:
            Callable: Wrapped method with message sanitisation.
        """

        @wraps(func)
        def wrapper(self, message, *args, **kwargs):
            if not isinstance(message, str):
                try:
                    message = str(message)
                except Exception as e:
                    print(e)
                    message = repr(message)

            # Step 2: sanitize for cp1252
            try:
                message = message.encode("cp1252", errors="replace").decode("cp1252")
            except Exception as e:
                print(e)
                message = message.encode("ascii", errors="replace").decode("ascii")

            return func(self, message, *args, **kwargs)

        return wrapper

    def process_stack(self, stack_: list) -> tuple[str, int]:
        """Generated: validation needed.

        Description:
            Walk the call stack and return filename and line number of the first
            frame outside this module.

        Args:
            stack_ (list): Frame list from :func:`inspect.stack`.

        Returns:
            tuple[str, int]: Caller filename (basename) and line number.

        Raises:
            ValueError: When no caller frame outside this module is found.
        """
        caller_frame = None
        for frame in stack_:
            name = __name__.replace(".", "\\")
            normalised_filename = frame.filename.replace("/", "\\")
            if name not in frame.filename and name not in normalised_filename:
                caller_frame = frame
                break

        if caller_frame is None:
            raise ValueError("No caller frame found")
        lineno = caller_frame.lineno
        filename = caller_frame.filename
        filename = filename.split("/")[-1]
        filename = filename.split("\\")[-1]
        return filename, lineno

    @fix_non_ascii_messages_decorator
    def debug(self, message, print_level=0, *args, **kwargs):
        stack_ = stack()
        filename, lineno = self.process_stack(stack_)
        self.logger.debug(
            message,
            extra={
                "print_level": print_level,
                "custom_filename": filename,
                "custom_lineno": lineno,
            },
        )

    @fix_non_ascii_messages_decorator
    def info(self, message, print_level=3, *args, **kwargs):
        stack_ = stack()
        filename, lineno = self.process_stack(stack_)
        self.logger.info(
            message,
            extra={
                "print_level": print_level,
                "custom_filename": filename,
                "custom_lineno": lineno,
            },
        )

    @fix_non_ascii_messages_decorator
    def warning(self, message, print_level=2, *args, **kwargs):
        stack_ = stack()
        filename, lineno = self.process_stack(stack_)
        self.logger.warning(
            message,
            extra={
                "print_level": print_level,
                "custom_filename": filename,
                "custom_lineno": lineno,
            },
        )

    @fix_non_ascii_messages_decorator
    def error(self, message, print_level=1, *args, **kwargs):
        stack_ = stack()
        filename, lineno = self.process_stack(stack_)
        self.logger.error(
            message,
            extra={
                "print_level": print_level,
                "custom_filename": filename,
                "custom_lineno": lineno,
            },
        )

    @fix_non_ascii_messages_decorator
    def critical(self, message, print_level=0, *args, **kwargs):
        stack_ = stack()
        filename, lineno = self.process_stack(stack_)
        self.logger.critical(
            message,
            extra={
                "print_level": print_level,
                "custom_filename": filename,
                "custom_lineno": lineno,
            },
        )

    def set_print_level(self, level: int) -> None:
        """Generated: validation needed.

        Description:
            Change the console handler print level dynamically.

        Args:
            level (int): New maximum print level to pass through to console.
        """
        self.print_level = level
        self.filter.print_level = level

    # def log(self, level, message, print_level=2):
    #     """Log messages with an additional print_level argument"""
    #     self.logger.log(level, message, extra={"print_level": print_level})

    @fix_non_ascii_messages_decorator
    def starting(self, message, print_level=4, *args, **kwargs):
        if self.logger.isEnabledFor(CustomLogger.STARTING_LEVEL):
            stack_ = stack()
            filename, lineno = self.process_stack(stack_)
            extra_new = {"custom_filename": filename, "print_level": print_level}
            # merge with new from args if it exists
            extra_new.update(kwargs.get("extra", {}))

            self.logger._log(
                CustomLogger.STARTING_LEVEL,
                message,
                args,
                extra=extra_new,
            )

    @fix_non_ascii_messages_decorator
    def finished(self, message, print_level=3, *args, **kwargs):
        if self.logger.isEnabledFor(CustomLogger.FINISHED_LEVEL):
            stack_ = stack()
            filename, lineno = self.process_stack(stack_)
            self.logger._log(
                CustomLogger.FINISHED_LEVEL,
                message,
                args,
                extra={
                    "custom_lineno": lineno,
                    "custom_filename": filename,
                    "print_level": print_level,
                },
            )

    @fix_non_ascii_messages_decorator
    def valid(self, message, print_level=3, *args, **kwargs):
        if self.logger.isEnabledFor(CustomLogger.VALID_LEVEL):
            stack_ = stack()
            filename, lineno = self.process_stack(stack_)
            self.logger._log(
                CustomLogger.VALID_LEVEL,
                message,
                args,
                extra={
                    "custom_lineno": lineno,
                    "custom_filename": filename,
                    "print_level": print_level,
                },
            )

    def _run_log_parser(self):
        df = parse_log_file(self.log_file_path)
        parsed_path = self.log_file_path.with_name(f"{self.log_file_path.stem}_parsed.csv")
        df.to_csv(parsed_path, index=False)
        if self.print_level <= 1:
            print(f"[Logger] Parsed log file saved to: {parsed_path}")


def progressBar(
    iterable,
    prefix="",
    suffix="",
    decimals=1,
    length=100,
    fill="█",
    printEnd="\n",
    start_time=None,
    current_print_level=2,
    print_level=2,
):
    """
    Taken from https://stackoverflow.com/questions/3173320/text-progress-bar-in-the-console
    Then modified by Jelle Bonthuis on 2025-01-23 to include time elapsed in the suffix
    Further modified by Jelle Bonthuis on 2025-03-24 to include print levels that
        works congruently with the CustomLogger class
    Call in a loop to create terminal progress bar
    @params:
        iterable    - Required  : iterable object (Iterable)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
        start_time  - Optional  : start time of the process (Float)
        current_print_level - Optional : current print level of the logger (Int)
        print_level - Optional : print level of the logger (Int)
    """
    total = len(iterable)
    if total == 0:
        return

    # Progress Bar Printing Function
    def printProgressBar(iteration, suffix_ori=suffix, start_time=start_time):
        suffix = suffix_ori
        if start_time is not None:
            time_elapsed = perf_counter() - start_time
            time_elapsed = round(time_elapsed, decimals)
            suffix = f"{suffix_ori} Time elapsed: {time_elapsed}s "

        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + "-" * (length - filledLength)
        print(f"{prefix} |{bar}| {percent}% {suffix} ", end=printEnd)

    # Initial Call
    if int(print_level) <= int(current_print_level):
        printProgressBar(0, suffix_ori=suffix, start_time=start_time)
    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item
        if int(print_level) <= int(current_print_level):
            printProgressBar(i + 1, suffix_ori=suffix, start_time=start_time)
    # Print New Line on Complete
    # print(f"{prefix} |{'█' * length}| 100% {suffix} ", end = printEnd)
    print()


class CustomFormatter(Formatter):
    VALID_LEVEL = 25
    STARTING_LEVEL = 21
    FINISHED_LEVEL = 22
    # taken from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
    cyan = "\x1b[36;20m"
    dark_blue = "\x1b[34;20m"
    white = "\x1b[66;20m"
    grey_orange = "\x1b[38;5;245m"
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    reset = "\x1b[0m"
    format = "%(asctime).19s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    FORMATS = {
        STARTING_LEVEL: cyan + format + reset,
        FINISHED_LEVEL: dark_blue + format + reset,
        VALID_LEVEL: green + format + reset,
        DEBUG: grey_orange + format + reset,
        INFO: white + format + reset,
        WARNING: yellow + format + reset,
        ERROR: red + format + reset,
        CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        if hasattr(record, "custom_lineno"):
            record.lineno = record.custom_lineno
        if hasattr(record, "custom_filename"):
            record.filename = record.custom_filename
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = Formatter(log_fmt)
        return formatter.format(record)


class PrintLevelFilter(Filter):
    def __init__(self, print_level):
        super().__init__()
        self.print_level = int(print_level)

    def filter(self, record):
        record_print_level = getattr(record, "print_level", 2)
        return record_print_level <= self.print_level


_backup_logger = CustomLogger(
    "backup_logger",
    Path(__file__).resolve().parent / "logs",
    print_level=DEFAULT_BACKUP_LOGGER_PRINT_LEVEL,
    auto_parse=True,
)


def decorator_provide_time_information_2(  # noqa: C901
    function: Optional[Callable] = None,
    *,
    print_level: Optional[int] = None,
    time_decimals: int = 4,
    backup_logger: CustomLogger | None = None,
) -> Callable:
    def inner_decorator(
        func: Callable,
    ) -> Callable:
        """
        Decorator that provides time information for a function
        :param function:
        :return:
        """

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = kwargs.get("logger", None)
            if logger is None:
                for arg in args:
                    if hasattr(arg, "logger"):
                        logger = arg.logger
                        break

            if logger is None:
                if backup_logger is not None:
                    logger = backup_logger
                else:
                    logger = _backup_logger

            effective_print_level = kwargs.get("print_level", print_level)
            if effective_print_level is None:
                effective_print_level = DEFAULT_DECORATOR_PRINT_LEVEL

            effective_time_decimals = kwargs.get("time_decimals", time_decimals)
            if effective_time_decimals is None:
                effective_time_decimals = DEFAULT_DECORATOR_TIME_DECIMALS

            start_time = perf_counter()
            if hasattr(func, "__name__"):
                function_name = str(func.__name__)
            else:
                function_name = str(func)
            function_name = function_name.replace("<", "").replace(">", "")
            lineno = getsourcelines(func)[1] + 1
            source_lines = getsourcelines(func)[0]
            end_lineno = lineno + len(source_lines) - 1

            logger.starting(
                f"Starting: {function_name}",
                extra={"custom_lineno": lineno},
                print_level=effective_print_level,
            )

            result = func(*args, **kwargs)

            elapsed_time = perf_counter() - start_time
            full_message = (
                f"Finished: {function_name} in:"
                f" {elapsed_time:.{effective_time_decimals}f} seconds"
            )
            logger.finished(
                full_message,
                extra={"custom_lineno": end_lineno},
                print_level=effective_print_level,
            )

            return result

        return wrapper

    if callable(function):
        return inner_decorator(function)
    else:
        return partial(
            decorator_provide_time_information_2,
            print_level=print_level,
            time_decimals=time_decimals,
            backup_logger=backup_logger,
        )


def decorator_provide_time_information(function: Callable) -> Callable:
    """
    Decorator that provides time information for a function
    This requires the function to be called from a class instance
        and the class instance to have a logger attribute
        # todo make this more general to not require specific class instances

    Parameters:
        function (Callable): The function to be decorated
    """

    return decorator_provide_time_information_2(function, print_level=2)


def profile_time(func: Callable) -> Callable:
    """Generated: validation needed.

    Description:
        Decorator that profiles a function using both cProfile and line_profiler,
        printing timing statistics to stdout.

    Args:
        func (Callable): Function to profile.

    Returns:
        Callable: Wrapped function that prints timing stats on each call.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = cast(Any, func).__name__
        print(f"\n--- Profiling (Time) for {func_name} ---")

        # Line profiler
        profiler = line_profiler.LineProfiler()
        profiler.add_function(func)

        # CProfile
        cprof = cProfile.Profile()
        cprof.enable()
        profiler.enable_by_count()

        result = profiler(func)(*args, **kwargs)

        profiler.disable_by_count()
        cprof.disable()

        # Print cProfile stats
        print("\n[cProfile Stats]")
        s = io.StringIO()
        ps = pstats.Stats(cprof, stream=s).sort_stats("cumtime")
        ps.print_stats(20)
        print(s.getvalue())

        # Print line_profiler stats
        print("[line_profiler Stats]")
        profiler.print_stats()

        return result

    return wrapper


def profile_memory_full(func: Callable) -> Callable:
    """Generated: validation needed.

    Description:
        Decorator that profiles memory usage of a function using tracemalloc,
        psutil, and memory_profiler, printing a full memory report to stdout.

    Args:
        func (Callable): Function to profile.

    Returns:
        Callable: Wrapped function that prints memory stats on each call.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = cast(Any, func).__name__
        print(f"\n--- Profiling (Memory) for {func_name} ---")
        start_time = perf_counter()

        # Start tracemalloc
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Start psutil measurement
        process = psutil.Process(getpid())
        mem_before = process.memory_info().rss / (1024**2)

        # Run with memory_profiler
        def _target():
            return func(*args, **kwargs)

        mem_usage, result = memory_usage(
            (_target,),
            retval=True,
            interval=0.05,
            timeout=None,
        )

        # End tracemalloc
        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")

        # End psutil measurement
        mem_after = process.memory_info().rss / (1024**2)

        print(f"\n[memory_profiler] Peak memory usage: {max(mem_usage):.2f} MiB")
        print(
            f"[psutil]       Start: {mem_before:.2f} MiB → End:"
            f" {mem_after:.2f} MiB (Δ {(mem_after - mem_before):.2f} MiB)"
        )
        print(f"[Execution time] {perf_counter() - start_time:.4f} seconds")

        print("\n[tracemalloc top 10 differences]")
        for stat in top_stats[:10]:
            print(stat)

        tracemalloc.stop()
        return result

    return wrapper


@profile_memory_full
def memory_checker(func, *args, **kwargs):
    return func(*args, **kwargs)


def custom_asdict(obj):
    if is_dataclass(obj):
        result = {}
        ignored = getattr(obj, "_ignore_fields", set())

        for f in fields(obj):
            if f.name in ignored:
                continue

            value = getattr(obj, f.name)
            result[f.name] = custom_asdict(value)
        return result

    elif isinstance(obj, list):
        return [custom_asdict(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: custom_asdict(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return tuple(custom_asdict(v) for v in obj)

    return obj


@profile_time
def time_checker(func, *args, **kwargs):
    return func(*args, **kwargs)
