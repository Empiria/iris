from routing import router


class _Session:
    def __init__(self):
        self.launched: bool = False

    def launch(self):
        if self.launched:
            return
        self.terminate()
        router.launch()
        self.launched = True

    def terminate(self):
        router.clear_cache()


session = _Session()
