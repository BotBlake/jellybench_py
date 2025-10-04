class CompTool:
    """Compatibility Tool for checking system compatibility."""

    def __init__(
        self,
        logger,
        system_info: dict,
        ffmpeg_binary: str | None = None,
        skip_prompts: bool | None = False,
    ) -> None:
        """
        Initializes the compatibility tool.

        :param logger: Logger instance.
        :param skip_prompts: If True, skips user prompts.
        :param system_info: System information dictionary.
        """
        self.logger = logger
        self.skip_prompts = skip_prompts
        self.system_info = system_info
        self.ffmpeg_binary = ffmpeg_binary
        self.devices = {
            "cpu": False,
            "gpu": {},
        }

    def set_gpu(self, idx: int) -> None:
        """Adds a GPU device to the compatibility check."""
        if idx not in self.devices["gpu"]:
            self.devices["gpu"][idx] = {
                "compatible": None,
                "limit": None,
            }
            self.logger.info(f"GPU {idx} added to the compatibility check list.")
        else:
            self.logger.warning(f"GPU {idx} already exists in the compatibility check.")

    def set_cpu(self, state: bool) -> None:
        """Adds a CPU device to the compatibility check."""
        self.devices["cpu"] = state
        self.logger.info("CPU added to the compatibility check list.")

    def set_ffmpeg_binary(self, ffmpeg_binary: str) -> None:
        """Sets the ffmpeg binary for the compatibility check."""
        self.ffmpeg_binary = ffmpeg_binary
        self.logger.info(f"FFmpeg binary set to {ffmpeg_binary}.")

    def run(self):
        """Runs the compatibility checks."""
        print("Running compatibility checks...")
        if self.devices["cpu"]:
            print("Running CPU compatibility check...")
        if self.devices["gpu"]:
            print("Running GPU compatibility check...")
            for idx, device in self.devices["gpu"].items():
                print(f"Checking GPU {idx}...")
                gpu_data = self.system_info["gpu"][idx]
                if gpu_data["vendor"] == "nvidia":
                    nvidia_handler()
                elif gpu_data["vendor"] == "amd":
                    amd_handler()
                elif gpu_data["vendor"] == "intel":
                    intel_handler()
                else:
                    print(f"Unknown GPU vendor: {gpu_data['vendor']}")
        pass  # Placeholder for actual implementation


def nvidia_handler():
    """Handles NVIDIA-specific compatibility checks."""
    print("NVIDIA GPU detected, checking driver limits...")
    pass  # Placeholder for actual implementation


def amd_handler():
    """Handles AMD-specific compatibility checks."""
    print("AMD GPU detected, checking compatibility...")
    pass  # Placeholder for actual implementation


def intel_handler():
    """Handles Intel-specific compatibility checks."""
    print("Intel GPU detected, checking compatibility...")
    pass  # Placeholder for actual implementation


# To be implemented
"""
def check_driver_limit_demo(device: dict, ffmpeg_binary: str, gpu_idx: int):
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
    successful_count, failure_reason = worker.test_command(command, ffmpeg_log)
    if successful_count == worker_ammount:
        print(" success!")

    elif 0 < successful_count < worker_ammount:
        print(styled(" limited!", [Style.BG_RED]))
        print(
            f"| > Your GPU driver does only allow {successful_count} concurrent NvEnc sessions!"
        )
        skip_device = confirm(
            message="| > Do you want to skip GPU tests?",
            default=False,
            automate=skip_prompts,
        )
        limited_driver = successful_count
    else:
        print(" Error!")
        print("| > Your GPU is not capable of running NvEnc Streams!")
        print(f"| > FFmpeg: {failure_reason}")
        print("| > Please run the tool again and disable GPU tests")
        exit()
    print(styled("Done", [Style.GREEN]))
    print()
    return limited_driver, skip_device

def test_command(ffmpeg_cmd: str, passed_logger: Logger):
    passed_logger.info(f"> > Running 1x ffmpeg {ffmpeg_cmd}")
    ffmpeg_cmd_list = shlex.split(ffmpeg_cmd)
    successful_stream_count = 0
    raw_worker_data = run_ffmpeg(1, ffmpeg_cmd_list, passed_logger)

    failure_reason = raw_worker_data[1]
    process_output = raw_worker_data[0]
    nvenc_limit_reasons = ["incompatible client key", "out of memory"]
    if failure_reason in nvenc_limit_reasons or failure_reason is None:
        success_pattern = r"Output #\d+, null, to 'pipe:'"
        successful_streams = re.findall(success_pattern, process_output)
        successful_stream_count = len(successful_streams)
    passed_logger.info("< < Finished ffmpeg")

    return successful_stream_count, failure_reason
"""
