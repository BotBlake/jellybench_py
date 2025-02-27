from dataclasses import dataclass
from enum import Enum


@dataclass
class CommandConfig:
    BASE_CMD: str
    WORKER_CMD: str


class Constants:
    DEFAULT_OUTPUT_JSON: str = "./output.json"
    DEFAULT_LOG_DIR: str = "./jellybench-log"
    DEFAULT_SERVER_URL: str = "https://hwa.jellyfin.org"
    NVENC_TEST_WINDOWS = CommandConfig(
        BASE_CMD="{ffmpeg} -y -hwaccel cuda -hwaccel_output_format cuda -t 50 -hwaccel_device {gpu} -f lavfi -i testsrc ",
        WORKER_CMD="-vf hwupload -fps_mode passthrough -c:a copy -c:v h264_nvenc -b:v {bitrate} -f null -",
    )
    NVENC_TEST_LINUX = CommandConfig(
        BASE_CMD="{ffmpeg} -y -vsync 0 -hwaccel cuda -hwaccel_output_format cuda  -t 50 -hwaccel_device {gpu} -f lavfi -i testsrc ",
        WORKER_CMD="-vf hwupload -c:a copy -c:v h264_nvenc -b:v {bitrate} -f null -",
    )
    MAXINT32 = 2147483647


class Style(Enum):
    RED: str = "\033[31m"
    GREEN: str = "\033[32m"
    YELLOW: str = "\033[33m"
    BLUE: str = "\033[34m"
    MAGENTA: str = "\033[35m"
    CYAN: str = "\033[36m"
    WHITE: str = "\033[37m"
    BG_RED: str = "\033[41m"
    BG_GREEN: str = "\033[42m"
    BG_YELLOW: str = "\033[43m"
    BG_BLUE: str = "\033[44m"
    BG_MAGENTA: str = "\033[45m"
    BG_CYAN: str = "\033[46m"
    BG_WHITE: str = "\033[47m"
    BG_BLACK: str = "\033[40m"
    RESET: str = "\033[0m"
    BOLD: str = "\033[1m"
    DIM: str = "\033[2m"
    ITALIC: str = "\033[3m"
    UNDERLINE: str = "\033[4m"
    BLINK: str = "\033[5m"
    REVERSE: str = "\033[7m"
    HIDDEN: str = "\033[8m"
    STRIKETHROUGH: str = "\033[9m"
