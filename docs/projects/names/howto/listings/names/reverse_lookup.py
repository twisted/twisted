"""
Lookup the reverse DNS pointer records for one or more IPv4 addresses.

$ python  docs/projects/names/examples/reverse-lookup.py 1.2.3.4  2.3.4.5  3.4.5.6  4.5.6.7
5.4.3.2.in-addr.arpa IN <PTR name=ALyon-651-1-21-5.w2-3.abo.wanadoo.fr ttl=172796>
6.5.4.3.in-addr.arpa IN <PTR name=n003-000-000-000.static.ge.com ttl=43196>
"""
# if __name__ == '__main__':
#     import sys
#     from twisted.internet import task
#     from reverse_lookup import main
#     task.react(main, sys.argv[1:])

from twisted.internet import defer
from twisted.names import client

def printResult(result):
    answers, authority, additional = result
    if answers:
        print(', '.join('{} IN {}'.format(a.name.name, a.payload) for a in answers))


def reverseNameFromIPAddress(address):
    return '.'.join(reversed(address.split('.'))) + '.in-addr.arpa'


def main(reactor, *ipAddresses):
    pending = []
    for addr in ipAddresses:
        pointerName = reverseNameFromIPAddress(addr)
        d = client.lookupPointer(pointerName, timeout=(1,))
        d.addCallback(printResult)
        pending.append(d)
    return defer.DeferredList(pending, consumeErrors=True)
