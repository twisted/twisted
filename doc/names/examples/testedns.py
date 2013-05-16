"""
This test script will issue two queries to the oarc edns test servers:
 * https://www.dns-oarc.net/oarc/services/replysizetest

The second query is an edns query advertising a udpPayloadSize of
4096.

This second query will receive a series of CNAME answers, each one
smaller than the last, and each with a target name which reflects the
size of the response. eg

    # ID:  28590
    # ANSWERS:  1
    <CNAME name=rst.x3827.rs.dns-oarc.net ttl=60>

    # ID:  28590
    # ANSWERS:  1
    <CNAME name=rst.x2027.rs.dns-oarc.net ttl=60>

    # ID:  28590
    # ANSWERS:  1
    <CNAME name=rst.x1002.rs.dns-oarc.net ttl=60>

    # ID:  28590
    # ANSWERS:  1
    <CNAME name=rst.x476.rs.dns-oarc.net ttl=60>
"""


from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.task import react
from twisted.names import dns



class DigDatagramController(object):
    def __init__(self, reactor):
        self.reactor = reactor
        self.queries = {}


    def pickID(self):
        """
        Return a unique ID for queries.
        """
        while True:
            id = dns.randomSource()
            if id not in self.queries:
                return id


    def query(self, address, qname, qtype, edns=False, timeout=1):
        p = dns.DNSDatagramProtocol(controller=self, reactor=self.reactor)
        queryID = self.pickID()
        m = dns.Message(id=queryID)
        if edns:
            m.additional.append(dns.OPTHeader(udpPayloadSize=4096))
        m.addQuery(qname, qtype)

        p.startListening()
        p.writeMessage(m, address)

        d = Deferred()
        self.reactor.callLater(timeout, self.closeQuery, queryID, d)

        return d


    def closeQuery(self, queryID, d):
        d.callback(self.queries.pop(queryID))

    def messageReceived(self, message, protocol, address):
        self.queries.setdefault(message.id, []).append(message)




def main(reactor):
    c = DigDatagramController(reactor)
    queries = DeferredList([
        c.query(('149.20.58.133', 53), b'rs.dns-oarc.net', dns.TXT, edns=False),
        c.query(('149.20.58.133', 53), b'rs.dns-oarc.net', dns.NS, edns=True),
        ])

    def printResults(results):
        def allMessages():
            for success, answers in results:
                for message in answers:
                    yield message

        for message in allMessages():
            message.maxSize = 4096
            print "# ID: ", message.id, " SIZE: ", len(message.toStr())
            print "# ANSWERS: ", len(message.answers)
            for a in message.answers:
                print a.payload
            # print ""
            # print "# AUTHORITY: ", len(message.authority)
            # for a in message.authority:
            #     print a.payload
            # print ""
            # print "# ADDITIONAL: ", len(message.additional)
            # for a in message.additional:
            #     print a.payload
            print ""

    queries.addCallback(printResults)
    return queries



if __name__ == '__main__':
    raise SystemExit(react(main))
