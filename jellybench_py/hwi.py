#!/usr/bin/env python3

# jellybench_py.hwi.py
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
import platform
import subprocess

import cpuinfo

if platform.system() == "Windows":
    import wmi  # type: ignore


def test_lshw():  # test if lshw is installed properly (Executable Path/ False)
    try:
        lshw_subproc = subprocess.run(
            ["which", "lshw"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if lshw_subproc.returncode == 0:
            lshw_path = lshw_subproc.stdout.strip()
            return lshw_path
        else:
            return False
    except FileNotFoundError:
        return False


def run_lshw(hardware):
    lshw_path = test_lshw()
    if not lshw_path:
        print("Error")
        print()
        print("ERROR: lshw not installed. You may install it and try again.")
        input("Press any key to exit")
        exit()
    hw_subproc = subprocess.run(
        [lshw_path, "-json", "-class", hardware],
        text=True,
        capture_output=True,
        stdin=subprocess.PIPE,
        universal_newlines=True,
    )
    hw_output = json.loads(hw_subproc.stdout)
    return hw_output


def run_macos_sp(type: str) -> dict:
    # available data types can be found here "https://real-world-systems.com/docs/system_profiler.1.html"
    # or by simply running `systep_profiler -listDataTypes`
    hw_subproc = subprocess.run(
        ["system_profiler", "-json", "-detailLevel", "mini", type],
        text=True,
        capture_output=True,
        stdin=subprocess.PIPE,
        universal_newlines=True,
    )
    return json.loads(hw_subproc.stdout)


def check_ven(vendor):
    if "intel" in vendor.lower():
        vendor = "intel"
    elif "amd" in vendor.lower() or "advanced micro devices" in vendor.lower():
        vendor = "amd"
    elif "nvidia" in vendor.lower():
        vendor = "nvidia"
    return vendor


def get_platform_id(platforms: list) -> str:
    for element in platforms:
        if platform.system().lower() == element["type"].lower():
            return element["id"]


def get_os_info() -> dict:
    required = [
        "pretty_name",
        "name",
        "version_id",
        "version",
        "version_codename",
        "id",
        "home_url",
        "support_url",
        "bug_report_url",
    ]
    os_element = dict()

    # Getting system name, release and version
    os_element["name"] = platform.system()
    os_element["version"] = platform.version()
    os_element["version_id"] = platform.release()

    # Filling all possible values
    if os_element["name"] == "Linux":
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    key, value = line.strip().split("=", 1)
                    value = value.strip('"')
                    if key.lower() in required:
                        os_element[key.lower()] = value
        except FileNotFoundError:
            os_element["pretty_name"] = "Linux (Unknown Distro)"
            os_element["id"] = "linux"

    elif os_element["name"] == "Windows":
        os_element["pretty_name"] = platform.system() + " " + platform.release()
        os_element["id"] = "windows"
        os_element["version_codename"] = "win32"
        os_element["home_url"] = "https://www.microsoft.com/windows"
        os_element["support_url"] = "https://support.microsoft.com"
        os_element["bug_report_url"] = "https://support.microsoft.com/contactus/"

    # macOS
    elif os_element["name"] == "Darwin":
        sp = run_macos_sp("SPSoftwareDataType")
        raw: str = sp["SPSoftwareDataType"][0]["os_version"].split()

        os_element["name"] = raw[0]
        os_element["id"] = "macos"
        os_element["version_codename"] = "darwin"
        os_element["version"] = raw[1]
        os_element["version_id"] = raw[1]
        os_element["pretty_name"] = raw[0] + " " + raw[1]
        os_element["home_url"] = "https://www.apple.com"
        os_element["support_url"] = "https://support.apple.com"
        os_element["bug_report_url"] = "https://www.apple.com/feedback/macos/"

    return os_element


def get_gpu_info() -> list:
    gpu_elements = list()
    if platform.system() == "Windows":
        c = wmi.WMI()
        gpus = c.Win32_VideoController()

        for i, gpu in enumerate(gpus):
            configuration = {
                "driver": gpu.DriverVersion.strip(),
            }

            vendor = gpu.AdapterCompatibility.strip().lower()
            gpu_element = {
                "id": f"GPU{i + 1}",
                "class": "display",
                "description": gpu.creationClassName.strip(),
                "product": gpu.Name,
                "vendor": check_ven(vendor),
                "physid": gpu.DeviceID.strip(),
                "businfo": gpu.PNPDeviceID.strip(),
                "configuration": configuration,
            }
            gpu_elements.append(gpu_element)

    elif platform.system() == "Linux":
        gpus_info = run_lshw("display")  # Display fetches info from lshw
        for gpu in gpus_info:
            if "vendor" not in gpu:
                if "product" in gpu:
                    gpu["vendor"] = check_ven(gpu["product"])
                else:
                    gpu["vendor"] = "Unknown"
            else:
                gpu["vendor"] = check_ven(gpu["vendor"])
            gpu_elements.append(gpu)

    # macOS
    elif platform.system() == "Darwin":
        sp = run_macos_sp("SPDisplaysDataType")
        gpus = sp["SPDisplaysDataType"]
        for i in range(len(gpus)):
            gpu = gpus[i]
            vendor = (
                gpu["spdisplays_vendor"][13:]
                if "sppci_vendor" in gpu["spdisplays_vendor"]
                else gpu["spdisplays_vendor"]
            )
            entry = {
                "id": str(i),
                "class": "display",
                "description": gpu["sppci_device_type"],
                "product": gpu["sppci_model"],
                "vendor": vendor,
                # "physid": "",
                # "businfo": gpu["sppci_bus"],
                # "configuration": gpu["spdisplays_mtlgpufamilysupport"],
            }

            gpu_elements.append(entry)

    else:
        print("Error")
        print()
        print("ERROR: Unsupported OS, Hardware information not supported")
        input("Press any key to exit")
        exit()
    return gpu_elements


def get_cpu_info() -> list:
    cpu_info = cpuinfo.get_cpu_info()
    cpu_elements = list()

    # This field might not exist on macOS
    if "vendor_id_raw" in cpu_info:
        vendor = cpu_info["vendor_id_raw"]
        if "intel" in vendor.lower():
            vendor = "Intel"
        elif "amd" in vendor.lower() or "advanced micro devices" in vendor.lower():
            vendor = "Amd"

    elif "Apple" in cpu_info["brand_raw"]:
        vendor = "Apple"

    else:
        vendor = "Generic CPU"

    # Some platforms don't provide hz_advertised, using 0 as placeholder
    if "hz_advertised" in cpu_info:
        cpu_hz = max(cpu_info["hz_advertised"])
    else:
        cpu_hz = 0

    cpu_element = {
        "product": cpu_info["brand_raw"],
        "vendor": vendor,
        "cores": cpu_info["count"],
        "architecture": cpu_info["arch_string_raw"],
        "hz_advertised": cpu_hz,
        # "capabilities": cpu_info["flags"],  <- Temporarily Ignoring CPU Features
    }
    cpu_elements.append(cpu_element)

    return cpu_elements


def get_ram_info() -> list:
    ram_modules = list()
    if platform.system() == "Windows":
        c = wmi.WMI()
        for ram in c.Win32_PhysicalMemory():
            capacity = int(ram.Capacity) // (1024**3)  # Convert bytes to gigabytes
            speed = ram.Speed
            form_factor = ram.FormFactor
            ram_module = {
                "id": ram.Tag.strip().replace(" ", "_"),
                "class": "memory",
                "physid": ram.PartNumber,
                "units": "gigabytes",
                "size": capacity,
                "vendor": ram.Manufacturer,
                "Speed": speed,
                "FormFactor": form_factor,
            }
            ram_modules.append(ram_module)
    elif platform.system() == "Linux":
        memory_info = run_lshw("memory")
        for memory in memory_info:
            if memory["id"] == "memory" and "size" in memory and "units" in memory:
                if memory["units"] == "bytes":
                    memory["units"] == "b"
                elif memory["units"] == "kilobytes":
                    memory["units"] == "kb"
                elif memory["units"] == "megabytes":
                    memory["units"] == "mb"
                elif memory["units"] == "gigabytes":
                    memory["units"] == "gb"
                ram_modules.append(memory)

    # macOS
    elif platform.system() == "Darwin":
        sp = run_macos_sp("SPMemoryDataType")
        for i in range(len(sp["SPMemoryDataType"])):
            raw = sp["SPMemoryDataType"][i]
            cap_info = raw["SPMemoryDataType"].split()
            entry = {
                "id": str(i),
                "class": "memory",
                "units": cap_info[1].lower(),
                "size": int(cap_info[0]),
                "vendor": raw["dimm_manufacturer"],
                "FormFactor": raw["dimm_type"],
            }
            ram_modules.append(entry)

    return ram_modules


def get_system_info() -> dict:
    system_info = {
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "memory": get_ram_info(),
        "gpu": get_gpu_info(),
    }
    return system_info


if __name__ == "__main__":
    system_info = get_system_info()
    print(json.dumps(system_info, indent=4))
