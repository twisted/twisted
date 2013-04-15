from twisted.tubes.tube import Pump
class LinesToIntegersOrCommands(Pump):
    def received(self, item):
        if item == 'SUM':
            return sum
        if item == 'PRODUCT':
            return product
        result = int(item)
        self.tube.deliver(result)

def product(numbers):
    result = 1
    for number in numbers:
        result *= number
    return result
