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
from json import JSONDecodeError, load

import click
import requests


def getPlatform(server_url: str) -> list:
    click.echo("| Fetch Supported Platforms...", nl=False)
    platforms = None
    try:
        response = requests.get(f"{server_url}/api/v1/TestDataApi/Platforms")
        if response.status_code == 200:
            click.echo(" success!")
            platforms = response.json()
        else:
            click.echo(" Error")
            click.echo(f"ERROR: Server replied with {response.status_code}")
            click.pause("Press any key to exit")
            exit()
    except Exception:
        click.echo(" Error")
        click.echo("ERROR: No connection to Server possible")
        exit()
    platforms = platforms["platforms"]
    return platforms


def getTestData(platformID: str, platforms_data: list, server_url: str) -> tuple:
    valid = True
    click.echo("| Loading tests... ", nl=False)

    # DevMode File Loading
    if platformID == "local" and platforms_data == "local":
        try:
            with open(server_url, "r") as file:
                data = load(file)
                click.echo(" success!")
                return valid, data
        except JSONDecodeError:
            click.echo(" Error")
            click.echo()
            click.echo(
                "ERROR: Failed to decode JSON. Please check the file format.", err=True
            )
            click.pause("Press any key to exit")
            exit()
        except Exception as e:
            click.echo(" Error")
            click.echo()
            click.echo(f"ERROR: {e}", err=True)
            exit()
        return False, None

    current_platform = None
    for platform in platforms_data:
        if platform["id"] == platformID and platform["supported"]:
            current_platform = platform["id"]
    if not current_platform:
        click.echo(" Error")
        click.echo("ERROR: Your Platform isnt Supported.")
        click.pause("Press any key to exit")
        exit()

    try:
        response = requests.get(
            f"{server_url}/api/v1/TestDataApi?platformId={current_platform}"
        )
        if response.status_code == 200:
            click.echo(" success!")
            test_data = response.json()
        elif response.status_code == 429:
            click.echo(" Error")
            click.echo(f"ERROR: Server replied with {response.status_code}")
            ratelimit_time = response.headers["retry-after"]
            click.echo(f"Ratelimited: Retry in {ratelimit_time}s")
            exit(1)
        else:
            click.echo(" Error")
            click.echo(f"ERROR: Server replied with {response.status_code}")
            click.pause("Press any key to exit")
            exit()
    except Exception:
        click.echo(" Error")
        click.echo("ERROR: No connection to Server possible")
        exit()
    return valid, test_data
