class SSHService:
    name = None # this is the ssh name for the service
    protocolMessages = {} # these map #'s -> protocol names
    def serviceStarted(self):
        """
        called when the service is active on the transport.
        """

    def packetReceived(self, messageType, packet):
        """
        called when we receieve a packet on the transport
        """
        f = getattr(self,'ssh_%s' % self.protocolMessages[messageType][4:], None)
        if f:
            f(packet)            
        else:                     
            print "couldn't handle", messageType
            print repr(packet[1:])
            self.transport.sendUnimplemented()