import os
import unittest

from src.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = dict(os.environ)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_missing_env(self) -> None:
        os.environ["MODE"] = "api"
        os.environ.pop("CLOUD_AHOY_API_KEY", None)
        os.environ.pop("FLYSTO_API_KEY", None)
        os.environ.pop("CLOUD_AHOY_EMAIL", None)
        os.environ.pop("CLOUD_AHOY_PASSWORD", None)

        with self.assertRaises(ConfigError):
            load_config()

    def test_loads_defaults(self) -> None:
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
