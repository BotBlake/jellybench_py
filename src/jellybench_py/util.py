import logging
import os
from datetime import datetime

from jellybench_py.constant import Style


def create_logger(
    name: str | None, filepath: str, *, debug: bool = False
) -> logging.Logger:
    """
    Helper function to create a logger with a FileHandler.
    """
    logger = logging.getLogger(name)
    # Clear any existing handlers if present
    if logger.hasHandlers():
        logger.handlers.clear()

    # Set logging level based on debug flag
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    # Create FileHandler for logging to the specified file
    file_handler = logging.FileHandler(filepath)
    file_handler.setLevel(level)

    # Define a standard log format
    formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    # Add the handler to the logger and disable propagation to parent loggers
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger


def styled(text: str, styles: list[Style]) -> str:
    # Return a styled string
    style = "".join([x.value for x in styles])
    return f"{style}{text}{Style.RESET.value}"


def confirm(
    message: str = "Continue",
    *,
    default: bool | None = None,
    automate: bool | None = None,
) -> bool:
    if automate:
        return default if default is not None else True
    prompts = {True: "(Y/n)", False: "(y/N)", None: "(y/n)"}
    full_message = f"{message} {prompts[default]}: "

    valid_inputs = {"y": True, "yes": True, "n": False, "no": False}
    if default is not None:
        valid_inputs[""] = default

    while (response := input(full_message).strip().lower()) not in valid_inputs:
        print("Error: invalid input")

    return valid_inputs[response]


def format_time(seconds: int) -> str:
    """
    Converts time in seconds to human-readable format.

    Args:
        seconds (int): Time in seconds.

    Returns:
        str: Formatted time string (e.g. "1h 2m", "3m 4s", etc.).
    """
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if seconds >= 60:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes}m {sec}s" if sec else f"{minutes}m"
    return f"{seconds}s"


def get_nvenc_session_limit(driver_version: int) -> int:
    """Determines the maximum number of NVENC sessions based on the NVIDIA driver version."""

    if driver_version >= 550:
        return 8
    if 530 <= driver_version < 550:
        return 5
    if driver_version <= 530:
        return 3
    return 0


def print_debug(*string: str, prefix: str = "|", **kwargs) -> None:
    print(styled(prefix, [Style.BG_MAGENTA, Style.WHITE]), *string, **kwargs)


def create_name(basename: str) -> str:
    run_dir = f"{basename}-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    return run_dir


def resolve_path(path: str, name: str) -> str:
    if "{run_dir}" in path:
        path = path.replace("{run_dir}", name)
    return os.path.abspath(path)
