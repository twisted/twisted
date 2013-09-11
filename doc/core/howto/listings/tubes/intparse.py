import operator
from twisted.tubes.tube import Pump

def reducer(operation, initializer):
    def reduction(values):
        return reduce(operation, values, initializer)
    return reduction

class LinesToIntegersOrCommands(Pump):
    def received(self, item):
        if item == 'SUM':
            result = reducer(operator.add, 0)
        elif item == 'PRODUCT':
            result = reducer(operator.mul, 1)
        else:
            result = int(item)
        self.tube.deliver(result)

def product(numbers):
    return reduce(operator.mul, numbers, 1)
