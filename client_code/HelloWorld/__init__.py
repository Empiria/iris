from ._anvil_designer import HelloWorldTemplate

header_content = """
Short meeting links, powered by [VDO.Ninja](https://vdo.ninja).
"""


class HelloWorld(HelloWorldTemplate):
    def __init__(self, **properties):
        self.header_text.content = header_content
        self.init_components(**properties)
