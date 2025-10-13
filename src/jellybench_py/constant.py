from dataclasses import dataclass
from enum import StrEnum


@dataclass
class CommandConfig:
    BASE_CMD: str
    WORKER_CMD: str


class Constants:
    DEFAULT_OUTPUT_JSON: str = "./jellybench_data/{run_dir}/output.json"
    DEFAULT_LOG_DIR: str = "./jellybench_data/{run_dir}/log"
    DEFAULT_SERVER_URL: str = "https://hwa.jellyfin.org"
    NVENC_TEST_WINDOWS = CommandConfig(
        BASE_CMD="{ffmpeg} -y -hwaccel cuda -hwaccel_output_format cuda -t 50 "
        "-hwaccel_device {gpu} -f lavfi -i testsrc ",
        WORKER_CMD="-vf hwupload -fps_mode passthrough -c:a copy -c:v h264_nvenc "
        "-b:v {bitrate} -f null -",
    )
    NVENC_TEST_LINUX = CommandConfig(
        BASE_CMD="{ffmpeg} -y -vsync 0 -hwaccel cuda -hwaccel_output_format cuda "
        "-t 50 -hwaccel_device {gpu} -f lavfi -i testsrc ",
        WORKER_CMD="-vf hwupload -c:a copy -c:v h264_nvenc -b:v {bitrate} -f null -",
    )
    MAXINT32 = 2147483647


class Style(StrEnum):
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_BLACK = "\033[40m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    STRIKETHROUGH = "\033[9m"
