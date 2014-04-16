from deferexex import adder

class MyExc(Exception):
    "A sample exception"

class MyObj:

    def blowUp(self, result):
        self.x = result
        raise MyExc("I can't go on!")

    def trapIt(self, failure):
        failure.trap(MyExc)
        print 'error (', failure.getErrorMessage(), '). x was:', self.x
        return self.x

    def onSuccess(self, result):
        print result + 3

    def whenTrapped(eslf, result):
        print 'Finally, result was', result

    def run(self, o):
        o.callRemote("add", 1, 2).addCallback(
            self.blowUp).addCallback(
            self.onSuccess).addErrback(
            self.trapIt).addCallback(
            self.whenTrapped)

MyObj().run(adder)
