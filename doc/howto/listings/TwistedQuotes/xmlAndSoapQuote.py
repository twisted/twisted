from twisted.web import soap, xmlrpc, resource, server
from TwistedQuotes import quoters
import os

quotefile = os.path.join(os.path.dirname(__file__), "quotes.txt")
quoter = quoters.FortuneQuoter([quotefile])

class XMLRPCQuoter(xmlrpc.XMLRPC):
    def xmlrpc_quote(self):
        return quoter.getQuote()
    
class SOAPQuoter(soap.SOAPPublisher):
    def soap_quote(self):
        return quoter.getQuote()

def main():
    from twisted.internet import reactor
    root = resource.Resource()
    root.putChild('RPC2', XMLRPCQuoter())
    root.putChild('SOAP', SOAPQuoter())
    reactor.listenTCP(7080, server.Site(root))
    reactor.run()

if __name__ == '__main__':
    main()

