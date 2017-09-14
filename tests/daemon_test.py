import os
import json
import time
import threading

import pytest

from tuxeatpi_common.cli import main_cli, set_daemon_class
from tuxeatpi_nlu_nuance.daemon import NLU
from tuxeatpi_common.message import Message, MqttClient
import paho.mqtt.client as paho


from click.testing import CliRunner

def shutdown(self):
    super(NLU, self).shutdown()

class TestDaemon(object):

    @classmethod
    def setup_class(self):
        workdir = "tests/workdir"
        intents = "intents"
        dialogs = "dialogs"
        from unittest.mock import MagicMock
        from pynuance import credentials
        credentials.save_cookies = MagicMock()
        from pynuance import nlu
        nlu.understand_text = _fake_nlu_text2
        self.nlu_daemon = NLU('nlu_test', workdir, intents, dialogs)
        self.nlu_daemon.settings.language = "en_US"
        self.disable = False
        self.enable = False
        self.speech = False
        self.nlutest = False

        def get_message(mqttc, obj, msg):
            payload = json.loads(msg.payload.decode())
            self.message = payload.get("data", {}).get("arguments", {})
            if msg.topic == "hotword/disable":
                self.disable = True
            elif msg.topic == "hotword/enable":
                self.enable = True
            elif msg.topic == "speech/say":
                self.speech = True
            elif msg.topic == "nlu_test/test":
                self.nlutest = True
            self.message_topic = msg.topic

        def main_loop():
            time.sleep(1)
        self.nlu_daemon.main_loop = main_loop

        def fake_registry():
            return {"nlu_test": {"state": "ALIVE"}}
        self.nlu_daemon.registry.read = fake_registry
        self.nlu_daemon.shutdown = shutdown



        self.mqtt_client = paho.Client()
        self.mqtt_client.connect("127.0.0.1", 1883, 60)
        self.mqtt_client.on_message = get_message
        self.mqtt_client.subscribe("hotword/disable", 0)
        self.mqtt_client.subscribe("hotword/enable", 0)
        self.mqtt_client.subscribe("speech/say", 0)
        self.mqtt_client.subscribe("nlu_test/test", 0)
        self.mqtt_client.loop_start()

    @classmethod
    def teardown_class(self):
        self.message = None
        self.nlu_daemon.settings.delete("/config/global")
        self.nlu_daemon.settings.delete("/config/nlu_test")
        self.nlu_daemon.settings.delete()
        self.nlu_daemon.registry.clear()
        try:  # CircleCI specific
            self.nlu_daemon.shutdown(self.nlu_daemon)
        except AttributeError:
            pass

    @pytest.mark.order1
    def test_time(self, capsys):
        t = threading.Thread(target=self.nlu_daemon.start)
        t = t.start()
#        time.sleep(1)
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
        assert self.nlu_daemon.app_id == "FAKE_app_id"
        assert self.nlu_daemon.app_key == "FAKE_app_key"
        assert self.nlu_daemon.username == "USERNAME"
        assert self.nlu_daemon.password == "PASSWORD"


        from pynuance import nlu
        nlu.understand_text = _fake_nlu_text2
        self.nlu_daemon.text("What time is it ?")
        time.sleep(1)

        assert self.speech == True
        assert self.nlutest == True
        
        # Check enable/disable hotword
        self.nlu_daemon._enable_hotword()
        self.nlu_daemon._disable_hotword()
        time.sleep(1)
        assert self.enable == True
        assert self.disable == True



        return


def _fake_nlu_text2(*args, **kargs):
    return {'NMAS_PRFX_SESSION_ID': 'FAKE',
            'NMAS_PRFX_TRANSACTION_ID': '1',
            'audio_transfer_info': {'audio_id': 1,
             'end_time': '20170914031931004',
             'nss_server': 'nss-server:1',
             'packages': [{'bytes': 640, 'time': '20170914031929988'},
              {'bytes': 640, 'time': '20170914031930916'}],
             'start_time': '20170914031929862'},
            'cadence_regulatable_result': 'completeRecognition',
            'final_response': 1,
            'message': 'query_response',
            'nlu_interpretation_results': {'final_response': 1,
             'payload': {'diagnostic_info': {'adk_dialog_manager_status': 'undefined',
               'application': 'FAKE',
               'context_tag': 'general',
               'ext_map_time': '0',
               'fieldId': 'dm_main',
               'int_map_time': '0',
               'nlps_host': 'FAKE',
               'nlps_ip': '172.17.70.5',
               'nlps_nlu_type': 'quicknludynamic',
               'nlps_profile': 'QUICKNLUDYN',
               'nlps_profile_package': 'QUICKNLU',
               'nlps_profile_package_version': 'FAKE',
               'nlps_version': 'FAKE',
               'nlu_annotator': 'FAKE',
               'nlu_component_flow': 'FAKE',
               'nlu_language': 'eng-USA',
               'nlu_use_literal_annotator': '0',
               'nlu_version': 'FAKE',
               'nmaid': 'FAKE',
               'qws_project_id': 'FAKE',
               'third_party_delay': '2',
               'timing': {'finalRespSentDelay': '106', 'intermediateRespSentDelay': '5'}},
              'interpretations': [{'action': {'intent': {'confidence': 1.0,
                  'value': 'nlu_test__test'}},
                'literal': 'What time is it'}],
              'type': 'nlu-1.0'},
             'payload_format': 'nlu-base',
             'payload_version': '1.0',
             'status': 'success'},
            'prompt': '',
            'result_format': 'nlu_interpretation_results',
            'result_type': 'NDSP_ASR_APP_CMD',
            'status_code': 0,
            'transaction_id': 1}
