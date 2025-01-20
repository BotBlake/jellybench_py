from dataclasses import dataclass
from enum import Enum


@dataclass
class Constants:
    DEFAULT_SERVER_URL: str = "https://hwa.jellyfin.org"

class Style(Enum):
    RED: str = '\033[31m'
    GREEN: str = '\033[32m'
    YELLOW: str = '\033[33m'
    BLUE: str = '\033[34m'
    MAGENTA: str = '\033[35m'
    CYAN: str = '\033[36m'
    WHITE: str = '\033[37m'
    RESET: str = '\033[0m'
    BOLD: str = '\033[1m'
    DIM: str = '\033[2m'
    ITALIC: str = '\033[3m'
    UNDERLINE: str = '\033[4m'
    BLINK: str = '\033[5m'
    REVERSE: str = '\033[7m'
    HIDDEN: str = '\033[8m'
    STRIKETHROUGH: str = '\033[9m'