import os
import json
import time
import threading
import shutil

import pytest

from tuxeatpi_common.cli import main_cli, set_daemon_class
from tuxeatpi_nlu_nuance.daemon import NLU
from tuxeatpi_common.message import Message


from click.testing import CliRunner

class TestIntent(object):

    @classmethod
    def setup_class(self):
        workdir = "tests/workdir"
        intents = "intents"
        dialogs = "dialogs"
        from unittest.mock import MagicMock
        from pynuance import credentials
        credentials.save_cookies = MagicMock()
        from pynuance import nlu
        self.nlu_daemon = NLU('nlu_test', workdir, intents, dialogs)
        self.nlu_daemon.settings.language = "en_US"

    @classmethod
    def teardown_class(self):
        self.message = None
        self.nlu_daemon.settings.delete("/config/global")
        self.nlu_daemon.settings.delete("/config/nlu_test")
        self.nlu_daemon.settings.delete()
        self.nlu_daemon.registry.clear()
        shutil.rmtree("tests/workdir")

    @pytest.mark.order1
    def test_send_intent(self, capsys):
        # Global
        global_config = {"language": "en_US",
                         "nlu_engine": "fake_nlu",
                         }
        self.nlu_daemon.settings.save(global_config, "global")
        # Config
        config = {"app_id": "FAKE_app_id",
                  "app_key": "FAKE_app_key",
                  "username": "USERNAME",
                  "password": "PASSWORD",
                  }
        self.nlu_daemon.settings.save(config)
        self.nlu_daemon.set_config(config)

        time.sleep(2)

        from pynuance import mix
        mix.list_models = list_models
        from unittest.mock import MagicMock
        mix.create_model = MagicMock()
        mix.upload_model = MagicMock()
        mix.train_model = MagicMock()
        mix.model_build_create = MagicMock()
        mix.model_build_list = model_build_list
        mix.model_build_attach = MagicMock()
        self.nlu_daemon.send_intent("fake_intent", "en_US", "nlu_test", "fakefile", "fake_intent_data")


def list_models(username, password, cookies_file):
    return [{"name": "model1"}]

def model_build_list(model, cookies_file):
    return [{'created_at': time.time(), 'build_status': 'COMPLETED'}]
