from tuxeatpi_common.intents import IntentsHandler


class NLUIntentsHandler(IntentsHandler):

    def __init__(self, component):
        IntentsHandler.__init__(self, component)

    def read(self, nlu_engine, recursive=True, wait=True):
        key = os.path.join("/intents_",
                           nlu_engine,
                           )
        try:
            return self.etcd_client.read(key, recursive=recursive, wait=wait)
        except etcd.EtcdWatchTimedOut:
            return
