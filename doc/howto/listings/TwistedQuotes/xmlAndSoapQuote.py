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
    from twisted.internet.app import Application
    app = Application("xmlrpc")
    root = resource.Resource()
    root.putChild('RPC2', XMLRPCQuoter())
    root.putChild('SOAP', SOAPQuoter())
    app.listenTCP(7080, server.Site(root))
    return app

application = main()

if __name__ == '__main__':
    application.run(save=0)

