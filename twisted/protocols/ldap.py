import pureldap
import pureber

from twisted.python import mutablestring

from twisted.protocols import protocol

class LDAPClient(protocol.Protocol):
    """An LDAP client"""

    onwire = {}
    buffer = mutablestring.MutableString()

    berdecoder = pureldap.LDAPBERDecoderContext_LDAPMessage(
        inherit=pureldap.LDAPBERDecoderContext(
        fallback=pureber.BERDecoderContext()))

    def dataReceived(self, recd):
        self.buffer.append(recd)
        while 1:
            try:
                o=pureber.ber2object(self.berdecoder, self.buffer)
            except pureldap.BERExceptionInsufficientData:
                o=None
            if not o:
                break
            self.handle(o)

    def connectionMade(self):
        """TCP connection has opened"""

    def connectionLost(self):
        """Called when TCP connection has been lost"""

    def queue(self, op, handler):
        msg=pureldap.LDAPMessage(op)
        assert not self.onwire.has_key(msg.id)
        if op.needs_answer:
            self.onwire[msg.id]=handler
        self.transport.write(str(msg))

    def handle(self, msg):
        assert isinstance(msg.value, pureldap.LDAPProtocolResponse)
        handler=self.onwire[msg.id]

        # Return true to mark request as fully handled
        if handler(msg.value):
            del self.onwire[msg.id]


    ##Bind
    def bind(self, dn='', auth=''):
        r=pureldap.LDAPBindRequest(dn=dn, auth=auth)
        self.queue(r, self.handle_bind_msg)

    def handle_bind_msg(self, resp):
        assert isinstance(resp, pureldap.LDAPBindResponse)
        assert resp.referral==None #TODO
        if resp.resultCode==0:
            self.handle_bind_success(resp.matchedDN,
                                     resp.serverSaslCreds)
        else:
            self.handle_bind_fail(resp.resultCode,
                                  resp.errorMessage)
        return 1

    def handle_bind_success(self, matchedDN, serverSaslCreds):
        pass

    def handle_bind_fail(self, resultCode, errorMessage):
        # maybe retry with other methods?
        # SASL has something relevent here
        #self.transport.loseConnection()
        raise

    ##Unbind
    def unbind(self):
        r=pureldap.LDAPUnbindRequest()
        self.queue(r)
        self.transport.loseConnection()


    ##Search is externalized into class LDAPSearch
        



class LDAPSearch:
    def __init__(self,
                 ldapclient,
                 baseObject='',
                 scope=pureldap.LDAP_SCOPE_wholeSubtree,
                 derefAliases=pureldap.LDAP_DEREF_neverDerefAliases,
                 sizeLimit=0,
                 timeLimit=0,
                 typesOnly=0,
                 filter=pureldap.LDAPFilterMatchAll,
                 attributes=[],
                 ):
        self.ldapclient=ldapclient
        r=pureldap.LDAPSearchRequest(baseObject=baseObject,
                                     scope=scope,
                                     derefAliases=derefAliases,
                                     sizeLimit=sizeLimit,
                                     timeLimit=timeLimit,
                                     typesOnly=typesOnly,
                                     filter=filter,
                                     attributes=attributes)
        self.ldapclient.queue(r, self.handle_search_msg)

    def handle_search_msg(self, msg):
        if isinstance(msg, pureldap.LDAPSearchResultDone):
            assert msg.referral==None #TODO
            if msg.resultCode==0:
                assert msg.matchedDN==''
                self.handle_success()
            else:
                self.handle_fail(msg.resultCode,
                                 msg.errorMessage)
            return 1
        else:
            assert isinstance(msg, pureldap.LDAPSearchResultEntry)
            self.handle_entry(msg.objectName, msg.attributes)
            
    def handle_success(self):
        pass

    def handle_fail(self, resultCode, errorMessage):
        pass

    def handle_entry(self, objectName, attributes):
        pass
