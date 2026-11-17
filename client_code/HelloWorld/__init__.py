from ._anvil_designer import HelloWorldTemplate


class HelloWorld(HelloWorldTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
