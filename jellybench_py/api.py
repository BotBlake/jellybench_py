#!/usr/bin/env python3

# jellybench_py.api.py
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
from json import JSONDecodeError, dumps, load

import requests

from jellybench_py.constant import Style
from jellybench_py.util import styled


def getPlatform(server_url: str) -> list:
    print("| Fetch Supported Platforms...", end="")
    platforms = None
    response = requests.get(f"{server_url}/api/v1/TestDataApi/Platforms")
    if response.status_code == 200:
        print(" success!")
        platforms = response.json()
    else:
        print(" Error")
        print(f"ERROR: Server replied with {response.status_code}")
        input("Press any key to exit")
        exit()
    platforms = platforms["platforms"]
    return platforms


def getTestData(platformID: str, platforms_data: list, server_url: str) -> tuple:
    valid = True
    print("| Loading tests... ", end="")

    # DevMode File Loading
    if platformID == "local" and platforms_data == "local":
        try:
            with open(server_url, "r") as file:
                data = load(file)
                print(" success!")
                return valid, data
        except JSONDecodeError:
            print(" Error")
            print()
            print(
                styled(
                    "ERROR: Failed to decode JSON. Please check the file format.",
                    [Style.RED, Style.BOLD],
                )
            )
            input("Press any key to exit")
            exit()
        return False, None

    current_platform = None
    for platform in platforms_data:
        if platform["id"] == platformID and platform["supported"]:
            current_platform = platform["id"]
    if not current_platform:
        print(" Error")
        print("ERROR: Your Platform isnt Supported.")
        input("Press any key to exit")
        exit()

    response = requests.get(
        f"{server_url}/api/v1/TestDataApi?platformId={current_platform}"
    )
    if response.status_code == 200:
        print(" success!")
        test_data = response.json()
    elif response.status_code == 429:
        print(" Error")
        print(f"ERROR: Server replied with {response.status_code}")
        ratelimit_time = response.headers["retry-after"]
        print(f"Ratelimited: Retry in {ratelimit_time}s")
        exit(1)
    else:
        print(" Error")
        print(
            styled(
                f"ERROR: Server replied with {response.status_code}",
                [Style.RED, Style.BOLD],
            )
        )
        input("Press any key to exit")
        exit()
    return valid, test_data


def upload(server_url: str, data: dict):
    api_url = f"{server_url}/api/v1/SubmissionApi"
    print(f"| Uploading to {server_url}... ", end="")

    headers = {"accept": "text/plain", "Content-Type": "application/json"}

    response = requests.post(api_url, json=data, headers=headers)
    if response.ok:
        print(" success!")
    else:
        print(" Error")
    print()

    # Display detailed information about the response
    print("\n--- Response Details ---")
    print(f"URL: {response.url}")
    print(f"Status Code: {response.status_code}")
    print(f"Reason: {response.reason}")
    print(f"Headers: {dumps(dict(response.headers), indent=4)}")
    print(f"Elapsed Time: {response.elapsed}")

    # Display the raw response content
    print("\n--- Raw Response Content ---")
    print(response.content)

    # Display the text response (decoded from bytes)
    print("\n--- Text Response Content ---")
    print(response.text)
