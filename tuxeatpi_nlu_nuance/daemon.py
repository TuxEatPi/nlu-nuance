"""Module defining NLU Nuance component"""
import logging
import os
import signal
import time

from tuxeatpi_common.daemon import TepBaseDaemon
from tuxeatpi_common.error import TuxEatPiError
from tuxeatpi_common.message import Message, is_mqtt_topic
from tuxeatpi_nlu_nuance.initializer import NLUInitializer
from pynuance import nlu
from pynuance import mix


CONFIDENCE_THRESHOLD = 0.7


class NLU(TepBaseDaemon):

    def __init__(self, name, workdir, intent_folder, dialog_folder, logging_level=logging.INFO):
        TepBaseDaemon.__init__(self, name, workdir, intent_folder, dialog_folder, logging_level)
        # TODO get from settings
        self.language = None
        self.app_id = None
        self.app_key = None
        self.username = None
        self.password = None
        self._initializer = NLUInitializer(self)
        self.models_folder = "models"
        self._cookies_file = os.path.abspath(os.path.join(self.workdir, "cookies.json"))

    def main_loop(self):
        """Watch for any changes in etcd intents folder and apply them"""
        for data in self.intents.eternal_watch(self.settings.nlu_engine):
            self.logger.info("New intent detected")
            _, _, _, language, context_tag, component_name, file_name = data.key.split("/")
            self.send_intent(context_tag, language, component_name, file_name, data.value)

    def set_config(self, config):
        """Save the configuration and reload the daemon"""
        # TODO improve this ? can be factorized ?
        for attr in ["app_id", "app_key", "username", "password"]:
            if attr not in config.keys():
                self.logger.error("Missing parameter {}".format(attr))
                return False
        # Set params
        self.app_id = config.get("app_id")
        self.app_key = config.get("app_key")
        self.username = config.get("username")
        self.password = config.get("password")
        return True

    @is_mqtt_topic("text")
    def text(self, text, context_tag="general"):
        """Try to understand a text"""
        self.logger.info("nlu/text called with test %s", text)
        # Start nlu
        raw_result = nlu.understand_text(self.app_id, self.app_key, context_tag,
                                         self.settings.language, text)
        self.logger.debug(raw_result)
        result = self._handle_nlu_return(raw_result).get("result", {})
        # We got a result
        if result is None or result["module"] is None:
            # TODO
            self.logger.error(result)
            return
        # Send request
        topic = "/".join((result["module"], result["capacity"]))
        data = {"arguments": result.get("arguments", {})}
        message = Message(topic=topic, data=data)
        self.logger.info("Publish %s with argument %s", message.topic, message.payload)
        self.publish(message)

    @is_mqtt_topic("audio")
    def audio(self, context_tag="general"):
        """Try to understand from microphone"""
        self.logger.info("nlu/audio called")
        print(self.settings.language)
        # Disabling hotword
        topic = "hotword/disable"
        data = {"arguments": {}}
        message = Message(topic=topic, data=data)
        self.logger.info("Publish %s with argument %s", message.topic, message.payload)
        self.publish(message)
        # Start nlu
        raw_result = nlu.understand_audio(self.app_id, self.app_key, context_tag,
                                          self.settings.language)
        # Enabling hotword
        topic = "hotword/enable"
        data = {"arguments": {}}
        message = Message(topic=topic, data=data)
        self.logger.info("Publish %s with argument %s", message.topic, message.payload)
        self.publish(message)
        # We got a result
        self.logger.debug(raw_result)
        if self._handle_nlu_return(raw_result) is None:
            # TODO do something ???
            return
        result = self._handle_nlu_return(raw_result).get("result", {})
        if result["module"] is None:
            # TODO
            self.logger.error(result)
            return
        topic = "/".join((result["module"], result["capacity"]))
        data = {"arguments": result.get("arguments", {})}
        message = Message(topic=topic, data=data)
        self.logger.info("Publish %s with argument %s", message.topic, message.payload)
        self.publish(message)

    @is_mqtt_topic("test")
    def test(self):
        """NLU test to"""
        self.logger.info("nlu/test called")
        data = {"arguments": {"text": self.get_dialog("i_understand")}}
        topic = "speak/say"
        message = Message(topic=topic, data=data)
        self.publish(message)

#    @is_mqtt_topic("send_intent")
    def send_intent(self, intent_name, intent_lang, component_name, intent_file, intent_data):
        """Send intent (model) to Nuance Mix and activate it"""
        intent_id = "/".join((intent_lang, intent_name, intent_file))
        self.logger.info("nlu/send_intent %s called", intent_id)
        # Change names to fix with Nuance Mix concepts
        model_name = intent_name
        model_lang = intent_lang
        model_file = intent_file
        model_data = intent_data
        model_fullname = model_name + "__" + model_lang
        # TODO create a better trsx file management
        # concat file with same lang/context in the same file (with xml parser)
        # check if new intent is added
        # check if old intent is deleted
        lang_folder = os.path.join(self.models_folder, model_lang)
        if not os.path.exists(lang_folder):
            os.makedirs(lang_folder)
        model_folder = os.path.join(lang_folder, model_name)
        if not os.path.exists(model_folder):
            os.makedirs(model_folder)
        comp_folder = os.path.join(model_folder, component_name)
        if not os.path.exists(comp_folder):
            os.makedirs(comp_folder)
        model_filepath = os.path.join(comp_folder, model_file)
        if os.path.isfile(model_filepath):
            with open(model_filepath, "r") as mfh:
                old_model_data = mfh.read()
            if old_model_data == model_data:
                # Content not changed, do nothing
                self.logger.info("Intent %s not changed", intent_id)
                return
        # save check model exists
        models = mix.list_models(None, None, self._cookies_file)
        # If models is None we need to renew cookies
        if models is None:
            # Get cookies file
            self._initializer.get_nuance_cookies(force=True)
            models = mix.list_models(None, None, self._cookies_file)
        # check model existence
        if model_fullname not in [m.get("name") for m in models]:
            # create model
            self.logger.info("Creating model %s/%s", model_lang, model_name)
            mix.create_model(model_fullname, model_lang, cookies_file=self._cookies_file)
        # Send file
        with open(model_filepath, "w") as mfh:
            mfh.write(model_data)
        mix.upload_model(model_fullname, model_filepath, cookies_file=self._cookies_file)
        self.logger.info("Uploading %s", intent_id)
        # Train model
        mix.train_model(model_fullname, cookies_file=self._cookies_file)
        self.logger.info("Training %s/%s/%s/%s",
                         model_lang, model_name, component_name, model_file)
        # Build and create a new version
        notes = ""
        mix.model_build_create(model_fullname, notes, cookies_file=self._cookies_file)
        self.logger.info("Create new build %s", intent_id)
        # Waiting for model build
        builds = mix.model_build_list(model_fullname, cookies_file=self._cookies_file)
        builds = sorted(builds, key=lambda x: x.get('created_at'))
        while builds[-1].get('build_status') in ('STARTED', 'PENDING'):
            time.sleep(2)
            builds = mix.model_build_list(model_fullname, cookies_file=self._cookies_file)
            builds = sorted(builds, key=lambda x: x.get('created_at'))
        if builds[-1].get('build_status') == 'FAILED':
            self.logger.error("Error building model")
            # TODO handle failed
        elif builds[-1].get('build_status') == 'COMPLETED':
            self.logger.info("Build for %s done", intent_id)
        # TODO handle other status
        # TODO detect if the attach is already done
        try:
            mix.model_build_attach(model_fullname, context_tag=model_name,
                                   cookies_file=self._cookies_file)
            self.logger.info("Build %s ready", intent_id)
        except Exception:
            # Build already attached
            # TODO clean this
            pass
        # Send message for result
        self.logger.info("Intent %s updated on Mix website", intent_id)

    @is_mqtt_topic("help")
    def help_(self):
        pass

    @is_mqtt_topic("shutdown")
    def shutdown(self):
        super(NLU, self).shutdown()
        os.kill(os.getpid(), signal.SIGTERM)

    @is_mqtt_topic("reload")
    def reload(self):
        pass

    def _handle_nlu_return(self, nlu_return):
        """Handle nlu return by parsing result and formatting result
        to be transmission ready
        """
        result = {"module": None,
                  "capacity": None,
                  "arguments": None,
                  "confidence": None,
                  "need_confirmation": False,
                  "error": None,
                  }
        interpretations = nlu_return.get("nlu_interpretation_results", {}).\
            get("payload", {}).get("interpretations", {})
        # TODO: what about if len(interpretations) > 1 ??
        self.logger.info("Nb interpretations: %s", len(interpretations))
        for interpretation in interpretations:
            intent = interpretation.get("action", {}).get("intent", {})
            self.logger.info("Intent: %s", intent.get("value"))
            result['confidence'] = intent.get("confidence")
            self.logger.info("Confidence: %s", result["confidence"])

            # Get concepts
            arguments = {}
            for name, data in interpretation.get("concepts", {}).items():
                arguments[name] = data[0].get('value')
            self.logger.info("Arguments: %s", arguments)
            # TODO log arguments
            if intent.get("value") == "NO_MATCH":
                # I don't understand :/
                # TODO improve me
                self.logger.critical("No intent matched")
                result['error'] = "no intent matched"
                tts = self.dialogs.get_dialog(self.settings.language, "not_understand")
                return

            # Check intent
            if len(intent.get("value").rsplit("__", 1)) != 2:
                # TODO improve me
                self.logger.critical("BAD Intent name: {}".format(intent.get("value")))
                result['error'] = "bad intent name - trsx files must me fixed"
                tts = self.dialogs.get_dialog(self.settings.language, "not_understand")
                return {"result": result, "tts": tts}

            module, capacity = intent.get("value").rsplit("__", 1)
            result['module'] = module.replace("__", ".")
            result['capacity'] = capacity
            result['arguments'] = arguments
            result['confidence'] = intent.get("confidence")
            if intent.get("confidence") < CONFIDENCE_THRESHOLD:
                # TODO improve me
                # I'm not sure to understand :/
                self.logger.info("Module: %s", module)
                self.logger.info("Capacity: %s", capacity)
                self.logger.info("Need confirmation - confidence: %s", result['confidence'])
                result['need_confirmation'] = True
                tts = self.dialogs.get_dialog(self.settings.language, "uncertain")
                return {"result": result, "tts": tts}

            # Return result
            error = result.pop("error")
            if error:
                return {"error": error, "result": result}
            return {"result": result}


class NLUError(TuxEatPiError):
    """Base class for NLU exceptions"""
    pass
