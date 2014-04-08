from deferexex import adder

def blowUp(result):
    raise Exception("I can't go on!")

def onSuccess(result):
    print result + 3

adder.callRemote("add", 1, 2).addCallback(blowUp).addCallback(onSuccess)
