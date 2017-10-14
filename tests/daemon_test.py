import os
import json
import time
import threading

import pytest
from wampy.peers import Client

from tuxeatpi_common.cli import main_cli, set_daemon_class
from tuxeatpi_nlu_nuance.daemon import NLU
from tuxeatpi_common.message import Message


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

        def get_message(message, meta):
            payload = json.loads(message)
            self.message = payload.get("data", {}).get("arguments", {})
            if meta['topic'] == "hotword.disable":
                self.disable = True
            elif meta['topic'] == "hotword.enable":
                self.enable = True
            elif meta['topic'] == "nlu_test.test":
                self.nlutest = True
            self.message_topic = meta['topic']

        def hotword_disable():
            self.disable = True

        def hotword_enable():
            self.enable = True

        def speech_say(text):
            self.speech = True

        def main_loop():
            time.sleep(1)
        self.nlu_daemon.main_loop = main_loop

        def fake_registry():
            return {"nlu_test": {"state": "ALIVE"}}
        self.nlu_daemon.registry.read = fake_registry
        self.nlu_daemon.shutdown = shutdown

        self.wamp_client = Client(realm="tuxeatpi")
        self.wamp_client.start()
        self.wamp_client.session._register_procedure("hotword.disable")
        setattr(self.wamp_client, "hotword.disable", hotword_disable)

        self.wamp_client.session._register_procedure("hotword.enable")
        setattr(self.wamp_client, "hotword.enable", hotword_enable)

        self.wamp_client.session._register_procedure("speech.say")
        setattr(self.wamp_client, "speech.say", speech_say)

        self.wamp_client.session._subscribe_to_topic(get_message, "nlu_test.test")


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
    def test_nlu(self, capsys):
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
        nlu.understand_audio = _fake_nlu_text2
        self.nlu_daemon.audio()
        time.sleep(1)
        assert self.disable == True
        assert self.enable == True


        nlu.understand_text = _fake_nlu_text2
        self.nlu_daemon.text("What time is it ?")
        time.sleep(1)

        self.nlu_daemon.test()

        assert self.speech == True

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
