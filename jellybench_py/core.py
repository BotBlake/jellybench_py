#!/usr/bin/env python3

# jellybench_py.core.py
# A transcoding hardware benchmarking client (for Jellyfin)
#    Copyright (C) 2024 BotBlake <B0TBlake@protonmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
##########################################################################################
import argparse
import json
import os
import textwrap
from hashlib import sha256
from math import ceil
from shutil import get_terminal_size, rmtree, unpack_archive

import progressbar
import requests

from jellybench_py import api, ffmpeg_log, hwi, worker
from jellybench_py.constant import Constants, Style
from jellybench_py.util import styled


def obtainSource(
    target_path: str, source_url: str, hash_dict: dict, name: str, quiet: bool
) -> tuple:
    def match_hash(hash_dict: dict) -> tuple:
        supported_hashes = [
            "sha256",
        ]  # list of currently supported hashing methods
        message = ""
        if not hash_dict:
            message = "Note: " + styled("No file hash provided!", [Style.YELLOW])
            return None, None, message

        for idx, hash in enumerate(hash_dict):
            if hash["type"] in supported_hashes:
                message = f"Note: Compatible hashing method found. Using {hash['type']}"
                return hash["type"], hash["hash"], message
        message = "Note: " + styled(
            "No compatible hashing method found.", [Style.YELLOW]
        )
        return None, None, message

    def calculate_sha256(file_path: str) -> str:
        # Calculate SHA256 checksum of a file
        sha256_hash = sha256()
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def download_file(url, file_path, filename):
        label = r'| "{filename}" ({size:.2f}MB)'
        try:
            # Send HTTP request to get the file
            response = requests.get(url, stream=True)

            # If the response status is not successful, return failure
            if response.status_code != 200:
                return False, response.status_code  # Unable to download file

            total_size = int(response.headers.get("content-length", 0))

            # If total_size is 0, assume there was a problem with the file size info
            if total_size == 0:
                return False, "Invalid file size"
            label = label.format(filename=filename, size=total_size / 1024.0 / 1024)

            with open(file_path, "wb") as file:
                # fa960a6a36cff9fb9df215ded55b57a1ac3285147849ef6be1d8ea63552ffc17
                # Initialize the progress bar
                total_chunks = ceil(total_size / 1024)
                widgets = [
                    f"{label}: ",
                    progressbar.Percentage(),
                    " ",
                    progressbar.Bar(marker="=", left="[", right="]"),
                    " ",
                    progressbar.ETA(),
                ]

                with progressbar.ProgressBar(
                    max_value=total_chunks, widgets=widgets
                ) as bar:
                    progress = 0  # Track progress manually
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            progress += 1
                            file.write(chunk)
                            file.flush()
                            bar.update(progress)

            return True, ""

        except requests.exceptions.RequestException:
            return False, "Request error"  # Network issues or invalid URL

    hash_algorithm, source_hash, hash_message = match_hash(hash_dict)

    target_path = os.path.realpath(target_path)  # Relative Path!
    filename = os.path.basename(source_url)  # Extract filename from the URL
    file_path = os.path.join(target_path, filename)  # path/filename

    if os.path.exists(file_path):  # if file already exists
        existing_checksum = None
        if hash_algorithm == "sha256":
            existing_checksum = calculate_sha256(file_path)  # checksum validation

        if existing_checksum == source_hash or source_hash is None:  # if valid/no sum
            print(" success!")
            if not quiet:
                print(hash_message)
            return True, file_path  # Checksum valid, no need to download again
        else:
            os.remove(file_path)  # Delete file if checksum doesn't match

    # Create target path if non present
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    success, message = download_file(source_url, file_path, name)
    if not success:
        return success, file_path

    downloaded_checksum = calculate_sha256(file_path)  # checksum validation
    # print(f"CHECKSUM: {downloaded_checksum}")
    if downloaded_checksum == source_hash or source_hash is None:  # if valid/no sum
        return True, file_path  # Checksum valid
    else:
        # os.remove(file_path)  # Delete file if checksum doesn't match
        print(f"\nSource hash is {source_hash} but we got {downloaded_checksum}.")
        return False, "Invalid Checksum!"  # Checksum invalid


def unpackArchive(archive_path, target_path):
    if os.path.exists(target_path):
        rmtree(target_path)
        print(
            "INFO: "
            + styled("Replacing existing files with validated ones.", [Style.CYAN])
        )
    os.makedirs(target_path)

    print("Unpacking Archive...", end="")
    if archive_path.endswith((".zip", ".tar.gz", ".tar.xz")):
        unpack_archive(archive_path, target_path)
    print(" success!")


def format_gpu_arg(system_os, gpu, gpu_idx):
    if system_os.lower() == "windows":
        return gpu_idx
    if system_os.lower() == "linux":
        return gpu["businfo"].replace("@", "-")


def benchmark(ffmpeg_cmd: str, debug_flag: bool, prog_bar) -> tuple:
    runs = []
    total_workers = 1
    run = True
    last_speed = -0.5  # to Assure first worker always has the required difference
    formatted_last_speed = "00.00"
    failure_reason = []
    if debug_flag:
        print(f"> > > > Workers: {total_workers}, Last Speed: {last_speed}")
    while run:
        if not debug_flag:
            prog_bar.label = f"Testing | Workers: {total_workers:02d} | Last Speed: {formatted_last_speed}"
            prog_bar.render_progress()
        output = worker.workMan(total_workers, ffmpeg_cmd)
        # First check if we continue Running:
        # Stop when first run failed
        if output[0] and total_workers == 1:
            run = False
            failure_reason.append(output[1])
        # When run after scaleback succeded:
        elif (last_speed < 1 and not output[0]) and last_speed != -0.5:
            limited = False
            if last_speed == -1:
                limited = True
            last_speed = output[1]["speed"]
            formatted_last_speed = f"{last_speed:05.2f}"
            if debug_flag:
                print(
                    f"> > > > Scaleback success! Limit: {limited}, Total Workers: {total_workers}, Speed: {last_speed}"
                )
            run = False

            if limited:
                failure_reason.append("limited")
            else:
                failure_reason.append("performance")
        # Scaleback when fail on 1<workers (NvEnc Limit) or on Speed<1 with 1<last added workers or on last_Speed = Scaleback
        elif (
            (total_workers > 1 and output[0])
            or (output[1]["speed"] < 1 and last_speed >= 2)
            or (last_speed == -1)
        ):
            if output[0]:  # Assign variables depending on Scaleback reason
                last_speed = -1
                formatted_last_speed = "sclbk"
            else:
                last_speed = output[1]["speed"]
                formatted_last_speed = f"{last_speed:05.2f}"
            total_workers -= 1
            if debug_flag:
                print(
                    f"> > > > Scaling back to: {total_workers}, Last Speed: {last_speed}"
                )
        elif output[0] and total_workers == 0:  # Fail when infinite scaleback
            run = False
            failure_reason.append(output[1])
            failure_reason.append("infinity_scaleback")
        elif output[1]["speed"] < 1:
            run = False
            failure_reason.append("performance")
        # elif output[1]["speed"]-last_speed < 0.5:
        #    run = False
        #    failure_reason.append("failed_inconclusive")
        else:  # When no failure happened
            runs.append(output[1])
            last_speed = output[1]["speed"]
            total_workers += int(last_speed)
            formatted_last_speed = f"{last_speed:05.2f}"
            if debug_flag:
                print(f"> > > > Workers: {total_workers}, Last Speed: {last_speed}")
    if debug_flag:
        print(f"> > > > Failed: {failure_reason}")
    if len(runs) > 0:
        max_streams = runs[(len(runs)) - 1]["workers"]
        result = {
            "max_streams": max_streams,
            "failure_reasons": failure_reason,
            "single_worker_speed": runs[(len(runs)) - 1]["speed"],
            "single_worker_rss_kb": runs[(len(runs)) - 1]["rss_kb"],
        }
        prog_bar.label = (
            f"Done    | Workers: {max_streams} | Last Speed: {formatted_last_speed}"
        )
        return True, runs, result
    else:
        prog_bar.label = "Skipped | Workers: 00 | Last Speed: 00.00"
        return False, runs, {}


def output_json(data, file_path, server_url):
    # Write the data to the JSON file
    if file_path:
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as json_file:
            json.dump(data, json_file, indent=4)
        print(f"Data successfully saved to {file_path}")
    else:
        # upload to server
        api.upload(server_url, data)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ffmpeg",
        dest="ffmpeg_path",
        type=str,
        default="./ffmpeg",
        help="Path for JellyfinFFMPEG download/execution (default: ./ffmpeg)",
    )

    parser.add_argument(
        "--videos",
        dest="video_path",
        type=str,
        default="./videos",
        help="Path for download of test files (SSD required) (default: ./videos)",
    )

    parser.add_argument(
        "--server",
        dest="server_url",
        type=str,
        default=Constants.DEFAULT_SERVER_URL,
        help=f"Server URL for test data and result submission (default: {Constants.DEFAULT_SERVER_URL})",
    )

    parser.add_argument(
        "--output_path",
        dest="output_path",
        type=str,
        default="./output.json",
        help="Path to the output JSON file (default: ./output.json)",
    )

    parser.add_argument(
        "--gpu",
        dest="gpu_input",
        type=int,
        required=False,
        help="Select which GPU to use for testing",
    )

    parser.add_argument(
        "--nocpu",
        dest="disable_cpu",
        action="store_true",
        help="Select whether or not to use your CPU(s) for testing",
    )

    parser.add_argument(
        "--debug",
        dest="debug_flag",
        action="store_true",
        help="Enable additional debug output",
    )
    return parser.parse_args()


def cli() -> None:
    """
    Python Transcoding Acceleration Benchmark Client made for Jellyfin Hardware Survey
    """
    args = parse_args()
    global debug
    debug = args.debug_flag

    print()
    print("Welcome to jellybench_py Cheeseburger Edition 🍔")
    print()

    ffmpeg_log.create_log()

    # Informative disclaimer text
    terminal_size = get_terminal_size((80, 20))
    terminal_width = terminal_size.columns

    print(styled("Disclaimer", [Style.BOLD]))
    discplaimer_text = "Please close all background programs and plug the device into a power source if it is running on battery power before starting the benchmark."

    indent = "| "
    discplaimer_text = textwrap.fill(
        text=discplaimer_text,
        width=terminal_width - 10,
        initial_indent=indent,
        subsequent_indent=indent,
    )
    print(discplaimer_text)
    if input("Confirm? [Y/N]: ").lower() not in ["yes", "y"]:
        exit(1)

    print()

    if args.debug_flag:
        print(
            styled("Dev Mode", [Style.BG_MAGENTA, Style.WHITE])
            + ": Special Features and Output enabled  "
            + styled("DO NOT UPLOAD RESULTS!", [Style.RED])
        )
        print()
    print(styled("System Initialization", [Style.BOLD]))

    if not args.server_url.startswith("http") and args.debug_flag:
        if os.path.exists(args.server_url):
            print(
                styled("|", [Style.BG_MAGENTA, Style.WHITE]) + " Using local test-file"
            )
            platforms = "local"
            platform_id = "local"
        else:
            print()
            print("ERROR: Invalid Server URL")
            input("Press any key to exit")
            exit()
    else:
        if args.server_url != Constants.DEFAULT_SERVER_URL:
            print(
                styled("|", [Style.BG_MAGENTA, Style.WHITE])
                + " Not using official Server!  "
                + styled("DO NOT UPLOAD RESULTS!", [Style.RED])
            )
        platforms = api.getPlatform(
            args.server_url
        )  # obtain list of (supported) Platforms + ID's
        platform_id = hwi.get_platform_id(platforms)

    print("| Obtaining System Information...", end="")
    system_info = hwi.get_system_info()
    print(" success!")
    print("| Detected System Config:")
    print(f"|   OS: {system_info['os']['pretty_name']}")
    for cpu in system_info["cpu"]:
        print(f"|   CPU: {cpu['product']}")
        print(f"|     Threads: {cpu['cores']}")
        if "architecture" in cpu:
            print(f"|     Arch: {cpu['architecture']}")

    print("|   RAM:")
    for ram in system_info["memory"]:
        vendor = ram["vendor"] if "vendor" in ram else "Generic"
        size = ram["size"]
        units = ram["units"]
        if units.lower() in ("b", "bytes"):
            size //= 1000
            units = "kb"

        if units.lower() in ("kb", "kilobytes"):
            size //= 1000
            units = "mb"

        print(f"|     - {vendor} {size} {units} {ram.get('FormFactor', 0)}")

    print("|   GPU(s):")
    for i, gpu in enumerate(system_info["gpu"], 1):
        print(f"|     {i}: {gpu['product']}")
    # input("Press any key to continue")

    # Logic for Hardware Selection
    supported_types = []

    # CPU Logic
    if not args.disable_cpu:
        supported_types.append("cpu")

    # GPU Logic
    gpus = system_info["gpu"]

    if len(gpus) > 1 and args.gpu_input is None:
        # print("\\")
        # print(" \\")
        # print("  \\_")
        print("Multiple GPU's detected. Please select one to continue.")
        # print()
        # print("| 0: No GPU tests")
        # for i, gpu in enumerate(gpus, 1):
        #     print(f"    | {i}: {gpu['product']}, {gpu['vendor']}")
        # print()
        gpu_input = None
        valid_indices = [str(x) for x in range(len(gpus) + 1)]
        while gpu_input not in valid_indices:
            if gpu_input is not None:
                print(
                    "Please select an available GPU by "
                    + "entering its index number into the prompt."
                )
            gpu_input = input("Select GPU (0 to disable GPU tests)")
        # print("   _")
        # print("  /")
        # print(" /")
        # print("/")

    gpu_idx = int(gpu_input) - 1

    # Appends the selected GPU to supported types
    if gpu_input != 0:
        supported_types.append(gpus[gpu_idx]["vendor"])

    # Error if all hardware disabled
    if gpu_input == 0 and args.disable_cpu:
        print()
        print("ERROR: All Hardware Disabled")
        input("Press any key to exit")
        exit()

    # Stop Hardware Selection logic

    valid, server_data = api.getTestData(platform_id, platforms, args.server_url)
    if not valid:
        print(f"Cancelled: {server_data}")
        exit()
    print(styled("Done", [Style.GREEN]))
    print()

    # Download ffmpeg
    ffmpeg_data = server_data["ffmpeg"]
    print(styled("Loading ffmpeg", [Style.BOLD]))
    print('| Searching local "ffmpeg" -', end="")
    ffmpeg_download = obtainSource(
        args.ffmpeg_path,
        ffmpeg_data["ffmpeg_source_url"],
        ffmpeg_data["ffmpeg_hashs"],
        "ffmpeg",
        quiet=False,
    )

    if ffmpeg_download[0] is False:
        print(f"An Error occured: {ffmpeg_download[1]}")
        input("Press any key to exit")
        exit()
    elif ffmpeg_download[1].endswith((".zip", ".tar.gz", ".tar.xz")):
        ffmpeg_files = f"{args.ffmpeg_path}/ffmpeg_files"
        unpackArchive(ffmpeg_download[1], ffmpeg_files)
        ffmpeg_binary = f"{ffmpeg_files}/ffmpeg"
        if system_info["os"]["id"] == "windows":
            ffmpeg_binary = f"{ffmpeg_binary}.exe"
    else:
        ffmpeg_binary = ffmpeg_download[1]
    ffmpeg_binary = os.path.abspath(ffmpeg_binary)
    ffmpeg_binary = ffmpeg_binary.replace("\\", "\\\\")
    print(styled("Done", [Style.GREEN]))
    print()

    # Downloading Videos
    files = server_data["tests"]
    print(styled("Obtaining Test-Files:", [Style.BOLD]))
    for file in files:
        name = os.path.basename(file["name"])
        print(f'| "{name}" - local -', end="")
        success, output = obtainSource(
            args.video_path, file["source_url"], file["source_hashs"], name, quiet=True
        )
        if not success:
            print(" Error")
            print("")
            print(f"The following Error occured: {output}")
            input("Press any key to exit")
            exit()
    print(styled("Done", [Style.GREEN]))
    print()

    # Count ammount of tests required to do:
    test_arg_count = 0
    for file in files:
        tests = file["data"]
        for test in tests:
            commands = test["arguments"]
            for command in commands:
                if command["type"] in supported_types:
                    test_arg_count += 1
    print(f"We will do {test_arg_count} tests.")

    if input("Do you want to continue?").lower() not in ["y", "yes"]:
        print("Exiting...")
        exit()

    benchmark_data = []
    print()
    label = "Define this label string please."
    widgets = [
        f"{label}: ",
        progressbar.Percentage(),
        " ",
        progressbar.Bar(marker="=", left="[", right="]"),
        " ",
        progressbar.ETA(),
    ]

    with progressbar.ProgressBar(max_value=test_arg_count, widgets=widgets)(
        length=test_arg_count, label="Starting Benchmark..."
    ) as prog_bar:
        for file in files:  # File Benchmarking Loop
            ffmpeg_log.set_test_header(file["name"])
            if args.debug_flag:
                print()
                print(f"| Current File: {file['name']}")
            filename = os.path.basename(file["source_url"])
            current_file = os.path.abspath(f"{args.video_path}/{filename}")
            current_file = current_file.replace("\\", "\\\\")
            tests = file["data"]
            for test in tests:
                if args.debug_flag:
                    print(
                        f"> > Current Test: {test['from_resolution']} - {test['to_resolution']}"
                    )
                commands = test["arguments"]
                for command in commands:
                    test_data = {}
                    if command["type"] in supported_types:
                        if args.debug_flag:
                            print(f"> > > Current Device: {command['type']}")
                        arguments = command["args"]
                        arguments = arguments.format(
                            video_file=current_file,
                            gpu=format_gpu_arg(
                                hwi.platform.system(), gpus[gpu_idx], gpu_idx
                            ),
                        )
                        test_cmd = f"{ffmpeg_binary} {arguments}"
                        ffmpeg_log.set_test_args(test_cmd)

                        valid, runs, result = benchmark(
                            test_cmd, args.debug_flag, prog_bar
                        )
                        if not args.debug_flag:
                            prog_bar.update(1)

                        test_data["id"] = test["id"]
                        test_data["type"] = command["type"]
                        if command["type"] != "cpu":
                            test_data["selected_gpu"] = gpu_idx
                            test_data["selected_cpu"] = None
                        else:
                            test_data["selected_gpu"] = None
                            test_data["selected_cpu"] = 0
                        test_data["runs"] = runs
                        test_data["results"] = result

                        if len(runs) >= 1:
                            benchmark_data.append(test_data)
    print("")  # Displaying Prompt, before attempting to output / build final dict
    print("Benchmark Done. Writing file to Output.")
    result_data = {
        "token": server_data["token"],
        "hwinfo": {"ffmpeg": ffmpeg_data, **system_info},
        "tests": benchmark_data,
    }
    output_json(result_data, args.output_path, args.server_url)
    if args.output_path:
        if input("Do you want to upload your results to the server? "):
            output_json(result_data, None, args.server_url)



def main():
    # function required by poetry entrypoint
    return cli(obj={})

if __name__ == "__main__":
    cli()