#!/usr/bin/env python3

# pytab.core.py
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
import json
import os
import textwrap
from hashlib import sha256
from shutil import get_terminal_size, rmtree, unpack_archive

import click
from requests import get as reqGet

from pytab import api, hwi, worker


def match_hash(hash_dict: dict, output: bool) -> tuple:
    supported_hashes = [
        "sha256",
    ]  # list of currently supported hashing methods

    if not hash_dict:
        if output:
            click.echo(
                "Note: "
                + click.style("This file cannot be hash-verified!", fg="yellow")
            )
        return None, None

    for hash in hash_dict:
        if hash in supported_hashes:
            if output:
                click.echo(f"Note: Compatible hashing method found. Using {hash}")
            return hash, hash_dict[hash]
    if output:
        click.echo(
            "Note: "
            + click.style("This Client cannot hash-verify this file!", fg="yellow")
        )
    return None, None


def calculate_sha256(file_path: str) -> str:
    # Calculate SHA256 checksum of a file
    sha256_hash = sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def obtainSource(
    target_path: str, source_url: str, hash_dict: dict, notify_on_download: bool
) -> tuple:
    hash_algorithm, source_hash = match_hash(hash_dict, notify_on_download)

    target_path = os.path.realpath(target_path)  # Relative Path!
    filename = os.path.basename(source_url)  # Extract filename from the URL
    file_path = os.path.join(target_path, filename)  # path/filename

    if os.path.exists(file_path):  # if file already exists
        existing_checksum = None
        if hash_algorithm == "sha256":
            existing_checksum = calculate_sha256(file_path)  # checksum validation

        if existing_checksum == source_hash or source_hash is None:  # if valid/no sum
            return True, file_path  # Checksum valid, no need to download again
        else:
            os.remove(file_path)  # Delete file if checksum doesn't match

    # Create target path if non present
    if not os.path.exists(target_path):
        os.makedirs(target_path)

    if notify_on_download:
        click.echo("Downloading file...", nl=False)

    try:  # Download file
        response = reqGet(source_url)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            if notify_on_download:
                click.echo(" success!")
        else:
            return False, response.status_code  # Unable to download file
    except Exception:
        return False, "Unknown Error!"  # Unable to download file
    downloaded_checksum = calculate_sha256(file_path)  # checksum validation
    if downloaded_checksum == source_hash or source_hash is None:  # if valid/no sum
        return True, file_path  # Checksum valid
    else:
        os.remove(file_path)  # Delete file if checksum doesn't match
        return False, "Invalid Checksum!"  # Checksum invalid


def unpackArchive(archive_path, target_path):
    if os.path.exists(target_path):
        rmtree(target_path)
        click.echo(
            "INFO: "
            + click.style("Replacing existing files with validated ones.", fg="cyan")
        )
    os.makedirs(target_path)

    click.echo("Unpacking Archive...", nl=False)
    if archive_path.endswith((".zip", ".tar.gz", ".tar.xz")):
        unpack_archive(archive_path, target_path)
    click.echo(" success!")


def format_gpu_arg(system_os, gpu, gpu_idx):
    vendor = gpu["vendor"]
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
        click.echo(f"> > > > Workers: {total_workers}, Last Speed: {last_speed}")
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
                click.echo(
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
                click.echo(
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
                click.echo(
                    f"> > > > Workers: {total_workers}, Last Speed: {last_speed}"
                )
    if debug_flag:
        click.echo(f"> > > > Failed: {failure_reason}")
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


def output_json(data, file_path):
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write the data to the JSON file
    if file_path:
        with open(file_path, "w") as json_file:
            json.dump(data, json_file, indent=4)
        click.echo(f"Data successfully saved to {file_path}")
    else:
        click.echo()
        click.echo("No output file specified. Writing to stdout.")
        click.echo(json.dumps(data, indent=4))


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=120)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--ffmpeg",
    "ffmpeg_path",
    type=click.Path(
        resolve_path=True,
        dir_okay=True,
        writable=True,
        executable=True,
    ),
    default="./ffmpeg",
    show_default=True,
    required=False,
    help="Path for JellyfinFFMPEG Download/execution",
)
@click.option(
    "--videos",
    "video_path",
    type=click.Path(
        resolve_path=True,
        dir_okay=True,
        writable=True,
        readable=True,
    ),
    default="./videos",
    show_default=True,
    required=False,
    help="Path for download of test files. (SSD required)",
)
@click.option(
    "--server",
    "server_url",
    default="https://hwa.jellyfin.org/",
    show_default=True,
    help="Server URL for test data and result submition.",
)
@click.option(
    "--output_path",
    type=click.Path(),
    default="./output.json",
    show_default=True,
    required=False,
    help="Path to the output JSON file.",
)
@click.option(
    "--gpu",
    "gpu_input",
    type=int,
    required=False,
    help="Select which gpu to use for testing",
)
@click.option(
    "--nocpu",
    "disable_cpu",
    type=bool,
    is_flag=True,
    required=False,
    default=False,
    help="Select whether or not to use your cpu(s) for testing",
)
@click.option(
    "--debug",
    "debug_flag",
    is_flag=True,
    default=False,
    help="Enable additional debug output",
)
def cli(
    ffmpeg_path: str,
    video_path: str,
    server_url: str,
    output_path: str,
    gpu_input: int,
    disable_cpu: bool,
    debug_flag: bool,
) -> None:
    """
    Python Transcoding Acceleration Benchmark Client made for Jellyfin Hardware Survey
    """
    global debug
    debug = debug_flag

    click.echo()
    click.echo("Welcome to PyTAB Cheeseburger Edition 🍔")
    click.echo()

    # Informative disclaimer text
    terminal_size = get_terminal_size((80, 20))
    terminal_width = terminal_size.columns

    click.echo(click.style("Disclaimer", bold=True))
    discplaimer_text = "Please close all background programs and plug the device into a power source if it is running on battery power before starting the benchmark."

    indent = "| "
    discplaimer_text = textwrap.fill(
        text=discplaimer_text,
        width=terminal_width - 10,
        initial_indent=indent,
        subsequent_indent=indent,
    )
    click.echo(discplaimer_text)
    click.confirm("Confirm")

    click.echo()

    if debug_flag:
        click.echo(
            click.style("Dev Mode", bg="magenta", fg="white")
            + ": Special Features and Output enabled  "
            + click.style("DO NOT UPLOAD RESULTS!", fg="red")
        )
        click.echo()
    click.echo(click.style("System Initialization", bold=True))

    if not server_url.startswith("http") and debug_flag:
        if os.path.exists(server_url):
            click.echo(
                click.style("|", bg="magenta", fg="white") + " Using local test-file"
            )
            platforms = "local"
            platform_id = "local"
        else:
            click.echo()
            click.echo("ERROR: Invalid Server URL", err=True)
            click.pause("Press any key to exit")
            exit()
    else:
        if not (server_url == "https://hwa.jellyfin.org/"):
            click.echo(
                click.style("|", bg="magenta", fg="white")
                + " Not using official Server!  "
                + click.style("DO NOT UPLOAD RESULTS!", fg="red")
            )
        platforms = api.getPlatform(
            server_url
        )  # obtain list of (supported) Platforms + ID's
        platform_id = hwi.get_platform_id(platforms)

    click.echo("| Obtaining System Information...", nl=False)
    system_info = hwi.get_system_info()
    click.echo(" success!")
    click.echo("| Detected System Config:")
    click.echo(f"|   OS: {system_info['os']['pretty_name']}")
    for cpu in system_info["cpu"]:
        click.echo(f"|   CPU: {cpu['product']}")
        click.echo(f"|     Threads: {cpu['cores']}")
        if "architecture" in cpu:
            click.echo(f"|     Arch: {cpu['architecture']}")

    click.echo("|   RAM:")
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

        click.echo(f"|     - {vendor} {size} {units} {ram.get('FormFactor', 0)}")

    click.echo("|   GPU(s):")
    for i, gpu in enumerate(system_info["gpu"], 1):
        click.echo(f"|     {i}: {gpu['product']}")
    # click.pause("Press any key to continue")

    # Logic for Hardware Selection
    supported_types = []

    # CPU Logic
    if not disable_cpu:
        supported_types.append("cpu")

    # GPU Logic
    gpus = system_info["gpu"]

    if len(gpus) > 1 and gpu_input is None:
        # click.echo("\\")
        # click.echo(" \\")
        # click.echo("  \\_")
        click.echo("Multiple GPU's detected. Please select one to continue.")
        # click.echo()
        # click.echo("| 0: No GPU tests")
        # for i, gpu in enumerate(gpus, 1):
        #     click.echo(f"    | {i}: {gpu['product']}, {gpu['vendor']}")
        # click.echo()
        gpu_input = click.prompt("Select GPU (0 to disable GPU tests)", type=int)
        # click.echo("   _")
        # click.echo("  /")
        # click.echo(" /")
        # click.echo("/")
    # checks to see if the flag or the selector were used
    # if not assigns input of the first GPU
    elif gpu_input is None:
        gpu_input = 1

    # Error if gpu_input is out of range
    if not (0 <= gpu_input <= len(gpus)):
        click.echo()
        click.echo("ERROR: Invalid GPU Input", err=True)
        click.pause("Press any key to exit")
        exit()

    gpu_idx = gpu_input - 1

    # Appends the selected GPU to supported types
    if gpu_input != 0:
        supported_types.append(gpus[gpu_idx]["vendor"])

    # Error if all hardware disabled
    if gpu_input == 0 and disable_cpu:
        click.echo()
        click.echo("ERROR: All Hardware Disabled", err=True)
        click.pause("Press any key to exit")
        exit()

    # Stop Hardware Selection logic

    valid, server_data = api.getTestData(platform_id, platforms, server_url)
    if not valid:
        click.echo(f"Cancled: {server_data}")
        exit()
    click.echo(click.style("Done", fg="green"))
    click.echo()

    # Download ffmpeg
    ffmpeg_data = server_data["ffmpeg"]
    click.echo(click.style("Loading ffmpeg", bold=True))

    ffmpeg_download = obtainSource(
        ffmpeg_path, ffmpeg_data["ffmpeg_source_url"], ffmpeg_data["ffmpeg_hashs"], True
    )

    if ffmpeg_download[0] is False:
        click.echo(f"An Error occured: {ffmpeg_download[1]}", err=True)
        click.pause("Press any key to exit")
        exit()
    elif ffmpeg_download[1].endswith((".zip", ".tar.gz", ".tar.xz")):
        ffmpeg_files = f"{ffmpeg_path}/ffmpeg_files"
        unpackArchive(ffmpeg_download[1], ffmpeg_files)
        ffmpeg_binary = f"{ffmpeg_files}/ffmpeg"
    else:
        ffmpeg_binary = ffmpeg_download[1]

    click.echo(click.style("Done", fg="green"))
    click.echo()

    # Downloading Videos
    files = server_data["tests"]
    click.echo(click.style("Obtaining Test-Files:", bold=True))
    for file in files:
        name = os.path.basename(file["name"])
        click.echo(f'| "{name}" -', nl=False)
        success, output = obtainSource(
            video_path, file["source_url"], file["source_hashs"], False
        )
        if success:
            click.echo(" success!")
        else:
            click.echo(" Error")
            click.echo("")
            click.echo(f"The following Error occured: {output}", err=True)
            click.pause("Press any key to exit")
            exit()
    click.echo(click.style("Done", fg="green"))
    click.echo()

    # Count ammount of tests required to do:
    test_arg_count = 0
    if not debug_flag:
        for file in files:
            tests = file["data"]
            for test in tests:
                commands = test["arguments"]
                for command in commands:
                    if command["type"] in supported_types:
                        test_arg_count += 1
        click.echo(f"We will do {test_arg_count} tests.")

    if not click.confirm("Do you want to continue?"):
        click.echo("Exiting...")
        exit()

    benchmark_data = []
    click.echo()

    with click.progressbar(
        length=test_arg_count, label="Starting Benchmark..."
    ) as prog_bar:
        for file in files:  # File Benchmarking Loop
            if debug_flag:
                click.echo()
                click.echo(f"| Current File: {file['name']}")
            filename = os.path.basename(file["source_url"])
            current_file = f"{video_path}/{filename}"
            tests = file["data"]
            for test in tests:
                if debug_flag:
                    click.echo(
                        f"> > Current Test: {test['from_resolution']} - {test['to_resolution']}"
                    )
                commands = test["arguments"]
                for command in commands:
                    test_data = {}
                    if command["type"] in supported_types:
                        if debug_flag:
                            click.echo(f"> > > Current Device: {command['type']}")
                        arguments = command["args"]
                        arguments = arguments.format(
                            video_file=current_file,
                            gpu=format_gpu_arg(
                                hwi.platform.system(), gpus[gpu_idx], gpu_idx
                            ),
                        )
                        test_cmd = f"{ffmpeg_binary} {arguments}"

                        valid, runs, result = benchmark(test_cmd, debug_flag, prog_bar)
                        if not debug_flag:
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
    click.echo("")  # Displaying Prompt, before attempting to output / build final dict
    click.echo("Benchmark Done. Writing file to Output.")
    result_data = {
        "token": server_data["token"],
        "hwinfo": system_info,
        "tests": benchmark_data,
    }
    output_json(result_data, output_path)


def main():
    return cli(obj={})


if __name__ == "__main__":
    cli()
