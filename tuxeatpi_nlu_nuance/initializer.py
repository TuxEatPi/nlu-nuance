"""Module customizing initialization for the Nuance NLU component"""
import os

from tuxeatpi_common.initializer import Initializer
from pynuance import credentials


class NLUInitializer(Initializer):
    """Custom initializer for the Nuance NLU component"""

    def __init__(self, component):
        Initializer.__init__(self, component)

    def get_nuance_cookies(self, force=False):
        """Get Nuance website cookies using username/password"""
        if not os.path.isfile(self.component._cookies_file) or force:
            self.logger.info("Get Mix cookies...")
            credentials.save_cookies(self.component._cookies_file,
                                     self.component.username,
                                     self.component.password)
            self.logger.info("... Get Mix saved")
        else:
            self.logger.info("Mix cookies already here")

    def run(self):
        """Run method overriding the standard one"""
        Initializer.run(self)
        # TODO check if this is needed
        self.get_nuance_cookies()
        intents = self.component.intents.read(self.component.settings.nlu_engine,
                                              recursive=True, wait=False)
        if intents is None:
            return
        for intent in intents.children:
            _, _, _, intent_lang, intent_name, component_name, file_name = intent.key.split("/")
            self.component.send_intent(intent_name, intent_lang, component_name,
                                       file_name, intent.value)
