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
