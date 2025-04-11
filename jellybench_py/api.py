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
from json import JSONDecodeError
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jellybench_py.util import format_time


class ApiError(Exception):
    """Custom exception for API errors."""

    pass


class ApiClient:
    def __init__(self, server_url: str, logger, timeout: int = 10) -> None:
        """
        Initializes the API client.

        :param server_url: The base URL of the API.
        :param logger: Logger instance, created using the `create_logger` function.
        :param timeout: Request timeout in seconds.
        """
        if not server_url.startswith("http"):
            raise ValueError("Invalid server URL provided.")

        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger
        self.session = requests.Session()
        self._configure_session()

    def _configure_session(self) -> None:
        """Configures a session with automatic retries for network errors."""
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.verify = True  # Ensure SSL certificate verification

    def get_platforms(self) -> List[Dict[str, Any]]:
        """
        Fetches the list of supported platforms from the API.

        :return: A list of platform dictionaries.
        :raises ApiError: If the request fails.
        """
        url = f"{self.server_url}/api/v1/TestDataApi/Platforms"
        self.logger.info("Fetching supported platforms from %s", url)

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            platforms_data = response.json()
            platforms = platforms_data.get("platforms", [])
            self.logger.info("Fetched %d platforms", len(platforms))
            return platforms
        except (requests.RequestException, JSONDecodeError) as e:
            self.logger.error("Error fetching platforms: %s", e)
            raise ApiError("Failed to fetch platforms") from e

    def get_test_data(self, platform_id: str) -> Dict[str, Any]:
        """
        Fetches test data for the given platform ID.

        :param platform_id: The platform ID for which to retrieve test data.
        :return: A dictionary containing test data.
        :raises ApiError: If the request fails.
        """
        url = f"{self.server_url}/api/v1/TestDataApi?platformId={platform_id}"
        self.logger.info("Fetching test data for platform %s from %s", platform_id, url)

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, JSONDecodeError) as e:
            self.logger.error("Error fetching test data: %s", e)
            retry_after = None
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                if e.response.status_code == 429:
                    retry_after = format_time(
                        int(e.response.headers.get("Retry-After", "0"))
                    )
                    self.logger.error(f"Server send retry_after: {retry_after}")
                    raise ApiError(
                        f"Too many requests - retry after {retry_after} secconds"
                    ) from e
            raise ApiError("Failed to fetch test data") from e

    def upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uploads benchmark results to the API.

        :param data: The benchmark result data to be uploaded.
        :return: A dictionary containing server response details.
        :raises ApiError: If the request fails.
        """
        api_url = f"{self.server_url}/api/v1/SubmissionApi"
        self.logger.info("Uploading data to %s", api_url)
        headers = {"Accept": "text/plain", "Content-Type": "application/json"}

        try:
            response = self.session.post(
                api_url, json=data, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            self.logger.info("Upload successful")
            return {
                "url": response.url,
                "status_code": response.status_code,
                "reason": response.reason,
                "headers": dict(response.headers),
                "elapsed": response.elapsed.total_seconds(),
                "content": response.content,
                "text": response.text,
            }
        except requests.RequestException as e:
            self.logger.error("Upload failed: %s", e)
            raise ApiError("Failed to upload data") from e
