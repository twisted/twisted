from twisted.web import soap, xmlrpc, resource, server
import os

def getQuote():
    return "Victory to the burgeois, you capitalist swine!"

class XMLRPCQuoter(xmlrpc.XMLRPC):
    def xmlrpc_quote(self):
        return getQuote()
    
class SOAPQuoter(soap.SOAPPublisher):
    def soap_quote(self):
        return getQuote()

def main():
    from twisted.internet import reactor
    root = resource.Resource()
    root.putChild('RPC2', XMLRPCQuoter())
    root.putChild('SOAP', SOAPQuoter())
    reactor.listenTCP(7080, server.Site(root))
    reactor.run()

if __name__ == '__main__':
    main()

