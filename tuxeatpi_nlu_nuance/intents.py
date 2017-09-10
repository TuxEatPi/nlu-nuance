"""Module customizing intents for the Nuance NLU component"""
import os

from tuxeatpi_common.intents import IntentsHandler


class NLUIntentsHandler(IntentsHandler):
    """Customi intents class for the Nuance NLU"""

    def __init__(self, component):
        IntentsHandler.__init__(self, component)

    def read(self, nlu_engine, recursive=True, wait=True, timeout=30):
        """Read all intents from Etcd"""
        key = os.path.join("/intents",
                           nlu_engine,
                           )
        return self.etcd_wrapper.read(key, recursive=recursive, wait=wait, timeout=timeout)
