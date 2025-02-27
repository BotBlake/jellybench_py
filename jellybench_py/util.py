import logging

from jellybench_py.constant import Style


def create_logger(name, filepath, debug_flag=False):
    """
    Helper function to create a logger with a FileHandler.
    """
    logger = logging.getLogger(name)
    # Clear any existing handlers if present
    if logger.hasHandlers():
        logger.handlers.clear()

    # Set logging level based on debug flag
    level = logging.DEBUG if debug_flag else logging.INFO
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
    message: str = "Continue", default: bool | None = None, automate: bool | None = None
) -> bool:
    if automate:
        if default is not None:
            return default
        else:
            return True
    prompts = {True: "(Y/n)", False: "(y/N)", None: "(y/n)"}
    full_message = f"{message} {prompts[default]}: "

    valid_inputs = {"y": True, "yes": True, "n": False, "no": False}
    if default is not None:
        valid_inputs[""] = default

    while (response := input(full_message).strip().lower()) not in valid_inputs:
        print("Error: invalid input")

    return valid_inputs[response]


def get_nvenc_session_limit(driver_version: int) -> int:
    if driver_version >= 550.0:
        return 8
    elif 530.0 <= driver_version < 550.0:
        return 5
    elif driver_version <= 530.0:
        return 3
    else:
        return 0


def print_debug(*string: str, prefix: str | None = "|", **kwargs):
    print(styled(prefix, [Style.BG_MAGENTA, Style.WHITE]), *string, **kwargs)
