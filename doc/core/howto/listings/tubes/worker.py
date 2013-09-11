from twisted.tubes.tube import Pump
class CommandsAndIntegersToResultIntegers(Pump):
    def __init__(self):
        self.buffer = []
    def received(self, item):
        if isinstance(item, int):
            self.buffer.append(item)
        else:
            items = self.buffer
            self.buffer = []
            result = item(items)
            self.tube.deliver(result)
