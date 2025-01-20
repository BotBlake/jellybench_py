from jellybench_py.constant import Style

def styled(text: str, styles: list[Style]) -> str:
    # Return a styled string
    style = ''.join([x.value for x in styles])
    return f"{style}{text}{Style.RESET.value}"