import os

global ffmpeg_log_path
ffmpeg_log_path = "./ffmpeg_err_log.txt"


def create_log():
    from time import ctime

    header = "jellybench_py: ffmpeg error log from "
    time_now = ctime(1627908313.717886)
    header = f"{header}{time_now}\n"
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(ffmpeg_log_path), exist_ok=True)

    # Write the data to the file
    if ffmpeg_log_path:
        with open(ffmpeg_log_path, "w") as ffmpeg_log_file:
            ffmpeg_log_file.write(time_now)


def set_test_header(header: str):
    # append the testfile-name to the file
    if ffmpeg_log_path:
        with open(ffmpeg_log_path, "a") as ffmpeg_log_file:
            ffmpeg_log_file.write(f"{header}\n")


def set_test_args(arguments):
    # append the command used to the file
    if ffmpeg_log_path:
        with open(ffmpeg_log_path, "a") as ffmpeg_log_file:
            ffmpeg_log_file.write(f"    -> {arguments}\n")


def set_test_error(errors):
    # append the command used to the file
    if ffmpeg_log_path:
        with open(ffmpeg_log_path, "a") as ffmpeg_log_file:
            for line in errors.splitlines():
                ffmpeg_log_file.write(f"        -| {line}\n")
            ffmpeg_log_file.write("        ----\n")
