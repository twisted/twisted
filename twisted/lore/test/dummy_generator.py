
"""
Module which pretends to be a generator for the unit tests.
"""

class DummyGenerator(object):
    def __init__(self, output, config):
        self.output = output
        self.initConfig = config


    def __call__(self, config, outfileGenerator):
        self.callConfig = config
        self.outfileGenerator = outfileGenerator
        return self


    def generate(self):
        pass


class DummyFactory(object):
    def getGenerator(self, output, config):
        return DummyGenerator(output, config)

factory = DummyFactory()
