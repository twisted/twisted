from twisted.web import microdom

class BadStream(Exception):
     pass

class XMLStream(microdom.MicroDOMParser):

    first = 1

    # if we get an exception in dataReceived we must send tag end before
    # losing connection

    def connectionMade(self):
        microdom.MicroDOMParser.connectionMade(self)
        self.transport.write("<stream:stream>")

    def loseConnection(self):
        self.transport.write("</stream:stream>")
        self.transport.loseConnection()

    def gotTagStart(self, name, attributes):
        if self.first:
            if name != "stream:stream":
                raise BadStream()
            self.first = 0
        else:
            microdom.MicroDOMParser.gotTagStart(self, name, attributes)

    def gotTagEnd(self, name):
        if not self.elementstack and name=="stream:stream":
            self.transport.loseConnection()
            return
        microdom.MicroDOMParser.gotTagEnd(self, name)
        if self.documents:
            self.gotElement(self.documents[0])
            self.documents.pop()

    def gotElement(self, element):
        raise NotImplementedError("what to do with element")

    def writeElement(self, element):
        element.writexml(self)

if __name__ == '__main__':
    from twisted.test.test_protocols import StringIOWithoutClosing
    from twisted.internet import protocol

    class XMLTester(XMLStream):
        def gotElement(self, element):
            print "got element"
            print element.toxml()
        def connectionLost(self):
            print "lost connection"

    x = XMLTester()
    t = StringIOWithoutClosing()
    x.makeConnection(protocol.FileWrapper(t))
    x.dataReceived('''
<stream:stream>
<message from='' to=''>
foobar
</message>
</stream:stream>
''')
