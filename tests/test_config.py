"""tests/test_config.py module."""
import os
import unittest

from src.core.config import load_config


class ConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        """Handle tearDown."""
        for key in list(os.environ.keys()):
            if key.startswith("CLOUD_AHOY_") or key.startswith("FLYSTO_") or key in {
                "MODE",
                "BROWSER_HEADLESS",
                "DRY_RUN",
                "MAX_FLIGHTS",
            }:
                os.environ.pop(key, None)

    def test_loads_defaults(self) -> None:
        """Test loads defaults."""
        os.environ["MODE"] = "api"
        os.environ["CLOUD_AHOY_API_KEY"] = "ca"
        os.environ["FLYSTO_API_KEY"] = "fs"
        os.environ["CLOUD_AHOY_EMAIL"] = "user@example.com"
        os.environ["CLOUD_AHOY_PASSWORD"] = "secret"

        config = load_config()

        self.assertEqual(config.cloudahoy_api_key, "ca")
        self.assertEqual(config.flysto_api_key, "fs")
        self.assertEqual(config.cloudahoy_base_url, "https://www.cloudahoy.com/api")
        self.assertEqual(config.flysto_base_url, "https://www.flysto.net")
        self.assertEqual(config.flysto_min_request_interval, 0.01)
        self.assertEqual(config.flysto_max_request_retries, 2)

    def test_loads_max_flights(self) -> None:
        """Test loads max flights."""
        os.environ["MODE"] = "api"
        os.environ["CLOUD_AHOY_API_KEY"] = "ca"
        os.environ["FLYSTO_API_KEY"] = "fs"
        os.environ["CLOUD_AHOY_EMAIL"] = "user@example.com"
        os.environ["CLOUD_AHOY_PASSWORD"] = "secret"
        os.environ["MAX_FLIGHTS"] = "12"

        config = load_config()

        self.assertEqual(config.max_flights, 12)

    def test_custom_flysto_throttle(self) -> None:
        """Test custom flysto throttle."""
        os.environ["MODE"] = "api"
        os.environ["CLOUD_AHOY_API_KEY"] = "ca"
        os.environ["FLYSTO_API_KEY"] = "fs"
        os.environ["CLOUD_AHOY_EMAIL"] = "user@example.com"
        os.environ["CLOUD_AHOY_PASSWORD"] = "secret"
        os.environ["FLYSTO_MIN_REQUEST_INTERVAL"] = "0.1"
        os.environ["FLYSTO_MAX_REQUEST_RETRIES"] = "5"

        config = load_config()

        self.assertEqual(config.flysto_min_request_interval, 0.1)
        self.assertEqual(config.flysto_max_request_retries, 5)


if __name__ == "__main__":
    unittest.main()
