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
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import cpuinfo

# Dataclasses and Enums for Hardware Information


@dataclass(slots=True)
class GPU:
    id: int
    description: str
    product: str
    vendor: GPU.Vendor
    physid: str
    businfo: str
    configuration: GPU.Configuration

    @dataclass(slots=True)
    class Configuration:
        driver: str | None

    class Vendor(str, Enum):
        NVIDIA = "nvidia"
        AMD = "amd"
        INTEL = "intel"
        UNKNOWN = "unknown"

        @classmethod
        def parse(cls, text: str | None) -> GPU.Vendor:
            if not text:
                return cls.UNKNOWN

            t = text.lower()
            if "nvidia" in t:
                return cls.NVIDIA
            if "amd" in t or "advanced micro devices" in t:
                return cls.AMD
            if "intel" in t:
                return cls.INTEL
            return cls.UNKNOWN


@dataclass(slots=True)
class CPU:
    product: str
    vendor: CPU.Vendor
    cores: int
    architecture: str
    hz_advertised: int | None

    class Vendor(str, Enum):
        APPLE = "apple"
        AMD = "amd"
        INTEL = "intel"
        UNKNOWN = "unknown"

        @classmethod
        def parse(cls, text: str | None) -> CPU.Vendor:
            if not text:
                return cls.UNKNOWN

            t = text.lower()
            if "intel" in t:
                return cls.INTEL
            if "amd" in t or "advanced micro devices" in t:
                return cls.AMD
            if "apple" in t:
                return cls.APPLE
            return cls.UNKNOWN


class PlatformManager:
    def __init__(self):
        pass

    def get_gpu_info(self) -> list[GPU]:
        return list[GPU]()

    def get_os_info(self) -> dict:
        return dict()


class HardwareManager:
    def __init__(self):
        self.platform = platform.system().lower()
        # HWA Server uses "mac" as id for macOS, but platform.system() returns "Darwin"
        self.platform = "mac" if self.platform == "darwin" else self.platform
        self.platform_manager = self._get_manager()

    def _get_manager(self) -> PlatformManager:
        if self.platform == "windows":
            return self.WindowsManager()
        if self.platform == "linux":
            return self.LinuxManager()
        if self.platform == "mac":
            return self.MacOSManager()
        raise NotImplementedError(f"Platform {self.platform} is not supported.")

    def get_system_info(self) -> dict:
        system_info = {
            "os": get_os_info(),
            "cpu": [asdict(cpu) for cpu in self.get_cpu_info()],
            # "memory": get_ram_info(),
            "gpu": [asdict(gpu) for gpu in self.platform_manager.get_gpu_info()],
        }
        return system_info

    def get_cpu_info(self) -> list[CPU]:
        cpu_info = cpuinfo.get_cpu_info()
        cpu_elements = []

        vendor = CPU.Vendor.parse(
            cpu_info.get(
                "vendor_id_raw",  # This might be missing on MacOS
                cpu_info.get("brand_raw", None),
            )
        )

        # Some platforms don't provide hz_advertised, using None as placeholder
        cpu_hz = max(cpu_info["hz_advertised"]) if "hz_advertised" in cpu_info else None

        cpu_element = CPU(
            product=cpu_info["brand_raw"],
            vendor=vendor,
            cores=cpu_info["count"],
            architecture=cpu_info["arch_string_raw"],
            hz_advertised=cpu_hz,
        )
        cpu_elements.append(cpu_element)

        return cpu_elements

    class WindowsManager(PlatformManager):
        def __init__(self):
            # Only Import wmi if WindowsManager is used (Wmi is Windows-only)
            import wmi  # type: ignore

            self.windows_management = wmi.WMI()

        def get_gpu_info(self) -> list[GPU]:
            gpu_elements = list[GPU]()
            gpus = self.windows_management.Win32_VideoController()

            for i, gpu in enumerate(gpus):
                driver = gpu.DriverVersion.strip()
                vendor = gpu.AdapterCompatibility.strip().lower()
                gpu_element = GPU(
                    id=i + 1,
                    description=gpu.creationClassName.strip(),
                    product=gpu.Name,
                    vendor=GPU.Vendor.parse(vendor),
                    physid=gpu.DeviceID.strip(),
                    businfo=gpu.PNPDeviceID.strip(),
                    configuration=GPU.Configuration(driver=driver if driver else None),
                )
                gpu_elements.append(gpu_element)
            return gpu_elements

    class LinuxManager(PlatformManager):
        def __init__(self):
            self.lshw_path = self._find_lshw()

        def _find_lshw(self) -> str:
            lshw_path = shutil.which("lshw")
            if not lshw_path:
                print("Error")
                print()
                print("ERROR: lshw not installed. You may install it and try again.")
                input("Press any key to exit")
                sys.exit()
            return lshw_path

        def _run_lshw(self, hardware_type: str) -> list[dict[str, Any]]:
            hw_subproc = subprocess.run(
                [self.lshw_path, "-json", "-class", hardware_type],
                text=True,
                capture_output=True,
                stdin=subprocess.PIPE,
            )
            hw_output = json.loads(hw_subproc.stdout)
            return hw_output

        def get_gpu_info(self) -> list[GPU]:
            gpu_elements = list[GPU]()
            gpus_info = self._run_lshw("display")  # Display fetches info from lshw
            gpu_id = 1
            for gpu in gpus_info:
                driver = gpu.get("configuration", {}).get("driver", None)
                vendor = GPU.Vendor.parse(gpu.get("vendor", gpu.get("product", None)))
                gpu_element = GPU(
                    id=gpu_id,
                    description=gpu.get("description", "Unknown"),
                    product=gpu.get("product", "Unknown"),
                    vendor=vendor,
                    physid=gpu.get("physid", ""),
                    businfo=gpu.get("businfo", ""),
                    configuration=GPU.Configuration(driver=driver),
                )
                gpu_elements.append(gpu_element)
                gpu_id += 1
            return gpu_elements

    class MacOSManager(PlatformManager):
        def __init__(self):
            print()

        def _run_macos_sp(self, hardware_type: str) -> dict[str, Any]:
            # available data types can be found here "https://real-world-systems.com/docs/system_profiler.1.html"
            # or by simply running `systep_profiler -listDataTypes`
            hw_subproc = subprocess.run(
                ["system_profiler", "-json", "-detailLevel", "mini", hardware_type],
                text=True,
                capture_output=True,
                stdin=subprocess.PIPE,
            )
            return json.loads(hw_subproc.stdout)

        def get_gpu_info(self) -> list[GPU]:
            gpu_elements = list[GPU]()
            gpus = self._run_macos_sp("SPDisplaysDataType")["SPDisplaysDataType"]
            for i, gpu in enumerate(gpus):
                vendor = GPU.Vendor.parse(
                    gpu["spdisplays_vendor"][13:]
                    if "sppci_vendor" in gpu["spdisplays_vendor"]
                    else gpu["spdisplays_vendor"]
                )
                gpu_element = GPU(
                    id=i + 1,
                    description=gpu["sppci_device_type"],
                    product=gpu["sppci_model"],
                    vendor=vendor,
                    physid="",
                    businfo=gpu["sppci_bus"],
                    configuration=GPU.Configuration(driver=None),
                )
                gpu_elements.append(gpu_element)
            return gpu_elements


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
    os_element = {}

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


def get_ram_info() -> list:
    ram_modules = []
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
                units = {
                    "bytes": "b",
                    "kilobytes": "kb",
                    "megabytes": "mb",
                    "gigabytes": "gb",
                }
                memory["units"] = units.get(memory["units"], memory["units"])
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


if __name__ == "__main__":
    hw_man = HardwareManager()
    system_info = hw_man.get_system_info()
    print(json.dumps(system_info, indent=4))
