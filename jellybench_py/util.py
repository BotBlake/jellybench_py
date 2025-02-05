from jellybench_py.constant import Style


def styled(text: str, styles: list[Style]) -> str:
    # Return a styled string
    style = "".join([x.value for x in styles])
    return f"{style}{text}{Style.RESET.value}"


def confirm(message: str = "Continue", default: bool | None = None) -> bool:
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


def print_debug(string: str):
    print(styled("|", [Style.BG_MAGENTA, Style.WHITE]), string)
