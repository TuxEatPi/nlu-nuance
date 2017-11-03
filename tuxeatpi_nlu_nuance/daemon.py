"""Module defining NLU Nuance component"""
import logging
import os
import signal
import time

from tuxeatpi_common.daemon import TepBaseDaemon
from tuxeatpi_common.error import TuxEatPiError
from tuxeatpi_common.message import Message
from tuxeatpi_common.wamp import is_wamp_topic, is_wamp_rpc
from tuxeatpi_nlu_nuance.initializer import NLUInitializer
from pynuance import nlu
from pynuance import mix


class NLU(TepBaseDaemon):
    """Nuance Communications Service based NLU component class"""

    def __init__(self, name, workdir, intent_folder, dialog_folder, logging_level=logging.INFO):
        TepBaseDaemon.__init__(self, name, workdir, intent_folder, dialog_folder, logging_level)
        # TODO get from settings
        self.language = None
        self.app_id = None
        self.app_key = None
        self.username = None
        self.password = None
        self._confidence_threshold = 0.7
        self._initializer = NLUInitializer(self)
        self.models_folder = os.path.abspath(os.path.join(self.workdir, "models"))
        self._cookies_file = os.path.abspath(os.path.join(self.workdir, "cookies.json"))

    def main_loop(self):
        """Watch for any changes in etcd intents folder and apply them"""
        # Handle shutdown
        time.sleep(1)
        for data in self.intents.eternal_watch(self.settings.nlu_engine):
            self.logger.info("New intent detected")
            _, _, _, language, context_tag, component_name, file_name = data.key.split("/")
            result = self.send_intent(context_tag, language, component_name, file_name, data.value)
            if result:
                self.build_model(context_tag, language)

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
        self._confidence_threshold = config.get("confidence_threshold", 0.7)
        return True

    @is_wamp_topic("text")
    def text(self, text, context_tag="general"):
        """Try to understand a text"""
        self.logger.info("nlu/text called with test %s", text)
        # Start nlu
        raw_result = nlu.understand_text(self.app_id, self.app_key, context_tag,
                                         text, self.settings.language)
        # We got a result
        self.logger.debug(raw_result)
        result = self._handle_nlu_return(raw_result)

        if result.get("error") in ('NO_MATCH', 'BAD_INTENT_NAME'):
            # No match
            self.logger.error(result)
            self.call("speech.say", text=self.get_dialog("not_understand"))
            return
        elif result.get("error") == "NEED_CONFIRMATION":
            self.logger.warning(result)
            self.call("speech.say", text=self.get_dialog("uncertain"))
            return
        elif result.get("error") == "CAN_NOT_DO_IT":
            self.logger.warning(result)
            self.call("speech.say", text=self.get_dialog("can_not_do_it"))
            return
        # Send request
        topic = "/".join((result["component"], result["capacity"]))
        data = {"arguments": result.get("arguments", {})}
        message = Message(topic=topic, data=data)
        self.logger.info("Publish %s with argument %s", message.topic, message.payload)
        self.publish(message)

    @is_wamp_rpc("audio")
    @is_wamp_topic("audio")
    def audio(self, context_tag="general"):
        """Try to understand from microphone"""
        self.logger.info("nlu/audio called")

        nlu_listening = True
        try:
            while nlu_listening:
                # Disable hotword
                self.call("hotword.disable")
                # Start nlu
                raw_result = nlu.understand_audio(self.app_id, self.app_key, context_tag,
                                                  self.settings.language)
                # We got a result
                self.logger.debug(raw_result)
                result = self._handle_nlu_return(raw_result)
                if result.get("error") == "NO_INTERPRETATION":
                    # No interpretation found
                    # This could mean: microphone muted, nobody spoke, ???
                    # For now, we just do nothing
                    self.logger.warning(result)
                    self.call("hotword.enable")
                    return
                elif result.get("error") in ('NO_MATCH', 'BAD_INTENT_NAME'):
                    # No match
                    self.logger.error("Error %s: %s", result.get("error"), result)
                    self.call("hotword.enable")
                    self.call("speech.say", text=self.get_dialog("not_understand"))
                    return
                elif result.get("error") == "NEED_CONFIRMATION":
                    # Confidence too low
                    self.logger.warning("Confirmation needed: %s", result)
                    self.call("hotword.enable")
                    self.call("speech.say", text=self.get_dialog("uncertain"))
                    # Quit if we want to exit
                    if not self._run_main_loop:
                        return
                    nlu_listening = True
                    continue
                elif result.get("error") == "CAN_NOT_DO_IT":
                    # missing component
                    self.logger.warning("Capacity not available: %s", result)
                    self.call("hotword.enable")
                    self.call("speech.say", text=self.get_dialog("can_not_do_it"))
                    return
                else:
                    # We can handle the intent
                    nlu_listening = False
                    self.call("hotword.enable")
                    # Send request
                    topic = ".".join((result["component"], result["capacity"]))
                    data = {"arguments": result.get("arguments", {})}
                    message = Message(topic=topic, data=data)
                    self.logger.info("Publish %s with argument %s", message.topic, message.payload)
                    self.publish(message)
                    return
        # TODO improve this except
        except Exception as exp:  # pylint: disable=W0703
            # Reenable hotword if we have an error
            self.logger.error(exp)
            self.call("hotword.enable")

    @is_wamp_topic("test")
    def test(self):
        """NLU test to"""
        self.logger.info("nlu/test called")
        self.call("speech.say", text=self.get_dialog("i_understand"))

    @is_wamp_topic("help")
    def help_(self):
        pass

    @is_wamp_topic("shutdown")
    def shutdown(self):
        super(NLU, self).shutdown()
        # TODO Etcd disconnection
        os.kill(os.getpid(), signal.SIGTERM)

    @is_wamp_topic("reload")
    def reload(self):
        pass

    def _handle_nlu_return(self, nlu_return):
        """Handle nlu return by parsing result and formatting result
        to be transmission ready
        """
        result = {"component": None,
                  "capacity": None,
                  "arguments": None,
                  "confidence": None,
                  "error": None,
                  }
        self.logger.debug(nlu_return)
        interpretations = nlu_return.get("nlu_interpretation_results", {}).\
            get("payload", {}).get("interpretations", {})
        self.logger.info("Literals: %s",
                         [i.get("literal") for i in interpretations])
        self.logger.info("Interpretations: %s",
                         [i.get("action", {}).get("intent", {}) for i in interpretations])
        # Not interpretations found
        if not interpretations:
            self.logger.warning("No interpretation found")
            result['error'] = "NO_INTERPRETATION"
            return result
        # TODO: what about if len(interpretations) > 1 ??
        interpretation = interpretations[0]
        # Process the first interpretation
        intent = interpretation.get("action", {}).get("intent", {})
        result['confidence'] = intent.get("confidence")
        # Check intents
        if intent.get("value") == "NO_MATCH":
            # I don't understand :/
            self.logger.critical("No intent matched")
            result['error'] = intent.get("value")
            return result
        # Check intent name
        if len(intent.get("value").rsplit("__", 1)) != 2:
            # TODO improve me
            # One intent was bad named in NLU....
            self.logger.critical("BAD Intent name: {}".format(intent.get("value")))
            result['error'] = "BAD_INTENT_NAME"
            return result
        # Check confidence
        if result['confidence'] < self._confidence_threshold:
            # TODO improve me
            # I'm not sure to understand :/
            self.logger.warning("Need confirmation - confidence: %s - %s",
                                result['confidence'], result)
            result['error'] = "NEED_CONFIRMATION"
            return result
        # Something was understood
        component, capacity = intent.get("value").rsplit("__", 1)
        # Check if the component is alive
        _states = self.registry.read()
        # TODO improve component/capacity check
        alive_components = [c for c, s in _states.items() if s.get('state') == 'ALIVE']
        if component not in alive_components:
            result['error'] = "CAN_NOT_DO_IT"
            return result
        # Get intent's arguments
        arguments = {}
        for name, data in interpretation.get("concepts", {}).items():
            arguments[name] = data[0].get('value')
        # Prepare result
        result['component'] = component.replace("__", ".")
        result['capacity'] = capacity
        result['arguments'] = arguments
        result['confidence'] = intent.get("confidence")
        self.logger.info("Result: %s", result)

        # Return result
        return result

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
                return False
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
        self.logger.info("Uploading %s", intent_id)
        mix.upload_model(model_fullname, model_data, cookies_file=self._cookies_file)
        # Send message for result
        self.logger.info("Intent %s updated on Mix website", intent_id)
        return True

    def build_model(self, model_name, model_lang):
        """Update model in Nuance Mix"""
        self.logger.info("Building %s/%s", model_lang, model_name)
        model_fullname = model_name + "__" + model_lang
        # Train model
        mix.train_model(model_fullname, cookies_file=self._cookies_file)
        self.logger.info("Training %s/%s", model_lang, model_name)
        # Build and create a new version
        notes = "Created by TuxEatPi"
        mix.model_build_create(model_fullname, notes, cookies_file=self._cookies_file)
        self.logger.info("Create new build %s", model_fullname)
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
            self.logger.info("Build for %s done", model_fullname)
        # TODO handle other status
        # TODO detect if the attach is already done
        try:
            mix.model_build_attach(model_fullname, context_tag=model_name,
                                   cookies_file=self._cookies_file)
            self.logger.info("Build %s ready", model_fullname)
        except Exception:  # pylint: disable=W0703
            # Build already attached
            # TODO clean this
            pass


class NLUError(TuxEatPiError):
    """Base class for NLU exceptions"""
    pass
