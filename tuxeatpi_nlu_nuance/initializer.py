import os

from tuxeatpi_common.initializer import Initializer
from pynuance import credentials


class NLUInitializer(Initializer):

    def __init__(self, component):
        Initializer.__init__(self, component)

    def get_nuance_cookies(self, force=False):
        if not os.path.isfile(self.component._cookies_file) or force:
            self.logger.info("Get Mix cookies...")
            credentials.save_cookies(self.component._cookies_file,
                                     self.component.username,
                                     self.component.password)
            self.logger.info("... Get Mix saved")
        else:
            self.logger.info("Mix cookies already here")

    def run(self):
        self.get_nuance_cookies()

        Initializer.run(self)
        intents = self.component.intents.read(self.component.settings.nlu_engine,
                                              recursive=True, wait=False)
        for intent in intents.children:
            _, _, _, intent_lang, intent_name, component_name, file_name = intent.key.split("/")
            self.component.send_intent(intent_name, intent_lang, component_name,
                                       file_name, intent.value)
