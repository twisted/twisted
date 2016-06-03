from __future__ import print_function

def successCallback(result):
    myResult = result + 1
    print(myResult)
    return myResult

...

adder.callRemote("add", 1, 1).addCallback(successCallback)
