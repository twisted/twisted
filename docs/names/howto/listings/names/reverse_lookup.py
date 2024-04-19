import sys

from twisted.internet import task
from twisted.names import client


def reverseNameFromIPAddress(address):
    return ".".join(reversed(address.split("."))) + ".in-addr.arpa"


def printResult(result):
    answers, authority, additional = result
    if answers:
        a = answers[0]
        print(f"{a.name.name} IN {a.payload}")


def main(reactor, address):
    d = client.lookupPointer(name=reverseNameFromIPAddress(address=address))
    d.addCallback(printResult)
    return d


task.react(main, sys.argv[1:])
