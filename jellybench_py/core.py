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
from math import ceil, floor
from shutil import get_terminal_size, rmtree, unpack_archive

import progressbar
import requests

from jellybench_py import api, ffmpeg_log, hwi, worker
from jellybench_py.constant import Constants, Style
from jellybench_py.util import confirm, get_nvenc_session_limit, print_debug, styled


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
                return hash["type"], hash["hash"].lower(), message
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

    if args.debug_flag:
        print()
        print_debug(f"> Target File Path: {file_path}")
        if args.ignore_hash:
            print_debug("> Server Provided Hashes:")
            for idx, item in enumerate(hash_dict):
                print_debug(f"> > {item['type']}: {item['hash']}")

    if os.path.exists(file_path):  # if file already exists
        existing_checksum = None
        if hash_algorithm == "sha256":
            existing_checksum = calculate_sha256(file_path)  # checksum validation

        if args.debug_flag and args.ignore_hash:
            print_debug("> Existing file hash:")
            print_debug(f"> > {hash_algorithm}: {existing_checksum}")

        if existing_checksum == source_hash or source_hash is None:  # if valid/no sum
            if args.debug_flag and args.ignore_hash:
                if source_hash:
                    print_debug(
                        "> Existing file hash matches server provided hash, skipping download."
                    )
                else:
                    print_debug("> No Server provided hash, skipping download.")
            print(" success!")
            if not quiet:
                print(hash_message)
            return True, file_path  # Checksum valid, no need to download again
        elif args.ignore_hash:
            print_debug("> Ignoring hash mismatch, using existing file.")
            return True, file_path
        else:
            if args.debug_flag:
                print_debug(
                    "> Existing file hash does not match server provided hash. Downloading new file"
                )
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
        if args.debug_flag and args.ignore_hash:
            print_debug("> File successfully verified with checksum")
        return True, file_path  # Checksum

    else:
        if args.debug_flag:
            print_debug("> Checksum failed, downloaded file hash:")
            print_debug(f"> > sha256: {downloaded_checksum}")

        if args.ignore_hash:
            print_debug("> Ignoring invalid checksum")
            return True, file_path
        else:
            if args.debug_flag:
                print_debug("> Expected file hash:")
                print_debug(f"> > sha256: {source_hash}")
            # os.remove(file_path)  # Delete file if checksum doesn't match
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


def benchmark(ffmpeg_cmd: str, debug_flag: bool, prog_bar, limit=0) -> tuple:
    # Blake Approved Wording
    # Test: One set of transcode parameters for a given file
    # Run: One iteration of the loop in this function

    runs = []
    total_workers = 1
    min_fail = (
        Constants.MAXINT32
    )  # some arbitrarily large number, using 32bit int limit
    max_pass = 0
    max_pass_run_data = {}
    failure_reason = []
    run = True
    last_speed = 0
    external_limited = (
        False  # Flag to save if run is being limited by external factors (eg. driver)
    )
    while run:
        assert max_pass < min_fail

        if debug_flag:
            print_debug(
                f"> > > > Starting run with {total_workers} Workers... ",
                end="",
                flush=True,
            )

        if prog_bar:  # Update Progress Bar if one exists
            prog_bar.update(
                status="Testing",
                workers=f"{total_workers:02d}",
                speed=f"{last_speed:.02f}",
            )

        output = worker.workMan(total_workers, ffmpeg_cmd)

        # output[0] boolean, Errored, False = no Errors, True = Errored
        # output[1] Run data if no errors, Error reason if errored

        # First check if we continue Running:
        # Stop if errored
        if output[0]:
            if args.debug_flag:
                print(f"failed with reason {output[1]}")
            failure_reason.append(output[1])
            break

        # exactly or faster than real time for this run

        elif output[1]["speed"] >= 1:
            max_pass = total_workers
            max_pass_run_data = output[1]

            if output[1]["speed"] > 1:
                total_workers = ceil(total_workers * output[1]["speed"])
            else:
                total_workers += 1

            # if limited end run
            if external_limited:
                run = False

        # slower than real time for this run
        elif output[1]["speed"] < 1:
            min_fail = total_workers
            total_workers *= floor(total_workers * output[1]["speed"])

        if args.debug_flag:
            print(f'completed with speed {output[1]["speed"]:.02f}')

        # make sure we don't go into already benchmarked region
        if total_workers >= min_fail:
            total_workers = min_fail - 1

        if total_workers <= max_pass:
            total_workers = max_pass + 1

        # Enforce external limit
        if limit and total_workers > limit:
            total_workers = limit
            external_limited = True

        if min_fail - max_pass == 1:
            run = False

        runs.append(output[1])
        last_speed = output[1]["speed"]

    # Process results

    # ffmpeg errored
    if failure_reason:
        pass

    # limited by nvidia driver
    elif external_limited:
        failure_reason.append("limited")

    elif min_fail - max_pass == 1:
        print_debug(
            f"> > > > Test Finished, Max Pass: {max_pass}, Min Fail: {min_fail}"
        )
        failure_reason.append("performance")

    else:
        failure_reason.append("failed_inconclusive")

    if debug_flag:
        print_debug(f"> > > > Failed: {failure_reason}")

    if len(runs) > 0:
        result = {
            "max_streams": max_pass,
            "failure_reasons": failure_reason,
            "single_worker_speed": max_pass_run_data["speed"],
            "single_worker_rss_kb": max_pass_run_data["rss_kb"],
        }
        prog_bar.update(status="Done", workers=max_pass, speed=f"{last_speed:.02f}")
        return True, runs, result
    else:
        prog_bar.label = "Skipped | Workers: 00 | Last Speed: 00.00"
        prog_bar.update(status="Skipped", workers=0, speed=0)
        return False, runs, {}


def check_driver_limit(device: dict, ffmpeg_binary: str, gpu_idx: int):
    def build_test_cmd(worker_ammount: int, ffmpeg_binary: str, gpu_arg) -> str:
        # Build an ffmpeg command to test {n}-concurrent NvEnc Streams
        if hwi.platform.system().lower() == "windows":
            base_cmd = Constants.NVENC_TEST_WINDOWS.BASE_CMD.format(
                ffmpeg=ffmpeg_binary, gpu=gpu_arg
            )
            worker_base = Constants.NVENC_TEST_WINDOWS.WORKER_CMD
        else:
            base_cmd = Constants.NVENC_TEST_LINUX.BASE_CMD.format(
                ffmpeg=ffmpeg_binary, gpu=gpu_arg
            )
            worker_base = Constants.NVENC_TEST_LINUX.WORKER_CMD
        worker_commands = []
        for i in range(1, worker_ammount + 1):
            bitrate = f"{i}M"
            worker_command = worker_base.format(bitrate=bitrate)
            worker_commands.append(worker_command)
        full_command = base_cmd + " ".join(worker_commands)
        return full_command

    def parse_driver(driver_raw: str) -> int:
        # parse windows specific driver output into NVIDIA Version (e.g. 32.0.15.6603 --> 566.03)
        split_driver = driver_raw.split(".")
        if len(split_driver) != 4:
            return -1

        major_version = list(split_driver[-2])
        if 0 < len(major_version):
            major_version = major_version[-1]
        else:
            return -1
        minor_version = split_driver[-1]

        if not (major_version.isdigit() and minor_version.isdigit()):
            return -1

        driver_version = float(major_version + minor_version) / 100
        limit = get_nvenc_session_limit(driver_version)
        print(
            f"| Your driver ({driver_version}) should only allow {limit} NvEnc sessions"
        )
        return limit

    limit = 8  # default driver limit

    if "configuration" in device and "driver" in device["configuration"]:
        driver_raw = device["configuration"]["driver"]
        driver_limit = parse_driver(driver_raw)
        if 0 < driver_limit:
            limit = driver_limit

    gpu_arg = format_gpu_arg(hwi.platform.system(), device, gpu_idx)
    worker_ammount = limit + 1
    print(f"| Testing with {worker_ammount} workers...", end="")
    command = build_test_cmd(worker_ammount, ffmpeg_binary, gpu_arg)

    skip_device = False
    limited_driver = 0
    successful_count, failure_reason = worker.test_command(command)
    if successful_count == worker_ammount:
        print(" success!")

    elif 0 < successful_count < worker_ammount:
        print(styled(" limited!", [Style.BG_RED]))
        print(
            f"| > Your GPU driver does only allow {successful_count} concurrent NvEnc sessions!"
        )
        skip_device = confirm(
            message="| > Do you want to skip GPU tests?", default=False
        )
        limited_driver = limit
    else:
        print(" Error!")
        print("| > Your GPU is not capable of running NvEnc Streams!")
        print(f"| > FFmpeg: {failure_reason}")
        print("| > Please run the tool again and disable GPU tests")
        exit()
    print(styled("Done", [Style.GREEN]))
    print()
    return limited_driver, skip_device


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


def only_do_upload_flow():
    # this is the main logic flow if the user passes only_do_upload flag
    print("Manual Upload. " + styled("USE WITH CAUTION!", [Style.RED]))
    output_file = args.output_path
    filename = os.path.basename(output_file)
    print(f'Uploading "{filename}" to "{args.server_url}"')
    if not confirm(default=True):
        exit()
    print()
    if not os.path.exists(output_file):
        print("Error. The file does not exist")
        exit()
    try:
        with open(output_file, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        print("Error: The file is not a valid JSON.")
        exit()
    api.upload(args.server_url, data)
    exit()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-U",
        dest="only_do_upload",
        action="store_true",
        help="Skip all tests and upload an existing json output file. Uses the default output path if you do not define --output_path.",
    )

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
        default=Constants.DEFAULT_OUTPUT_JSON,
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

    parser.add_argument(
        "--ignorehash",
        dest="ignore_hash",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def cli() -> None:
    """
    Python Transcoding Acceleration Benchmark Client made for Jellyfin Hardware Survey
    """
    global args
    args = parse_args()

    print()
    print("Welcome to jellybench_py Cheeseburger Edition 🍔")
    print()

    if args.only_do_upload:
        only_do_upload_flow()

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
    if not confirm():
        exit(1)

    print()

    if args.debug_flag:
        print_debug(
            ": Special Features and Output enabled",
            styled("DO NOT UPLOAD RESULTS!", [Style.RED]),
            prefix="Dev Mode",
        )
        print()
    print(styled("System Initialization", [Style.BOLD]))

    if not args.server_url.startswith("http") and args.debug_flag:
        if os.path.exists(args.server_url):
            print_debug(" Using local test-file")
            platforms = "local"
            platform_id = "local"
        else:
            print()
            print("ERROR: Invalid Server URL")
            input("Press any key to exit")
            exit()
    else:
        if args.server_url != Constants.DEFAULT_SERVER_URL:
            print_debug(
                " Not using official Server!",
                styled("DO NOT UPLOAD RESULTS!", [Style.RED]),
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
        valid_indices = [str(x) for x in range(len(gpus) + 1)]
        while args.gpu_input not in valid_indices:
            if args.gpu_input is not None:
                print(
                    "Please select an available GPU by "
                    + "entering its index number into the prompt."
                )
            args.gpu_input = input("Select GPU (0 to disable GPU tests): ")
        args.gpu_input = int(args.gpu_input)
        # print("   _")
        # print("  /")
        # print(" /")
        # print("/")
    elif len(gpus) == 1 and args.gpu_input is None:
        args.gpu_input = 1
    elif len(gpus) == 0:
        args.gpu_input = 0

    gpu = None
    gpu_idx = int(args.gpu_input) - 1

    # Appends the selected GPU to supported types
    if args.gpu_input != 0:
        gpu = gpus[gpu_idx]
        supported_types.append(gpu["vendor"])

    # Error if all hardware disabled
    if args.gpu_input == 0 and args.disable_cpu:
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
    print('| Searching local "ffmpeg"...', end="")
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

    # Test for NvEnc Limits
    if gpu and gpu["vendor"] == "nvidia":
        print(styled("Testing for driver limits: ", [Style.BOLD]) + "(NVIDIA)")
        limited_driver, skip_device = check_driver_limit(gpu, ffmpeg_binary, gpu_idx)
        if skip_device:
            supported_types.remove("nvidia")

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

    if not confirm():
        exit()

    benchmark_data = []
    print()
    widgets = [
        progressbar.Variable(
            "status", format=styled("Status: ", [Style.GREEN]) + "{formatted_value}  "
        ),
        progressbar.Variable(
            "workers",
            format=styled("Workers: ", [Style.GREEN]) + "{formatted_value}",
            width=4,
            precision=2,
        ),
        progressbar.Variable(
            "speed",
            format=styled("Last Speed: ", [Style.GREEN]) + "{formatted_value}",
            width=8,
            precision=6,
        ),
        progressbar.Percentage(),
        " ",
        progressbar.Bar(marker="=", left="[", right="]"),
        " ",
        progressbar.ETA(),
    ]

    prog_bar = None
    if not args.debug_flag:
        prog_bar = progressbar.ProgressBar(max_value=test_arg_count, widgets=widgets)

    progress = 0
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
                        gpu=format_gpu_arg(hwi.platform.system(), gpu, gpu_idx),
                    )
                    test_cmd = f"{ffmpeg_binary} {arguments}"
                    ffmpeg_log.set_test_args(test_cmd)

                    # cap nvidia limit
                    limit = 0
                    if command["type"] == "nvidia":
                        limit = limited_driver

                    valid, runs, result = benchmark(
                        test_cmd, args.debug_flag, prog_bar, limit=limit
                    )
                    if prog_bar:  # only update is progress bar exists
                        progress += 1
                        prog_bar.update(progress)
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
    if prog_bar:
        prog_bar.finish()  # Ensure the progress bar properly finishes if it was used
    print("")
    print("Benchmark Done. Writing file to Output.")
    result_data = {
        "token": server_data["token"],
        "hwinfo": {"ffmpeg": ffmpeg_data, **system_info},
        "tests": benchmark_data,
    }
    output_json(result_data, args.output_path, args.server_url)
    if args.output_path:
        if confirm(message="Upload results to server?", default=True):
            output_json(result_data, None, args.server_url)


def main():
    return cli()


if __name__ == "__main__":
    main()
