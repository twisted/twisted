# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""LDAP protocol client"""

from twisted.protocols import pureldap, pureber

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

    def queue(self, op, handler=None):
        msg=pureldap.LDAPMessage(op)
        assert not self.onwire.has_key(msg.id)
        assert op.needs_answer or not handler
        if op.needs_answer:
            self.onwire[msg.id]=handler
        self.transport.write(str(msg))

    def handle(self, msg):
        assert isinstance(msg.value, pureldap.LDAPProtocolResponse)
        handler=self.onwire[msg.id]

        # Return true to mark request as fully handled
        if handler==None or handler(msg.value):
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
        

class LDAPOperation:
    def __init__(self, client):
        self.client=client

class LDAPSearch(LDAPOperation):
    def __init__(self,
                 client,
                 baseObject='',
                 scope=pureldap.LDAP_SCOPE_wholeSubtree,
                 derefAliases=pureldap.LDAP_DEREF_neverDerefAliases,
                 sizeLimit=0,
                 timeLimit=0,
                 typesOnly=0,
                 filter=pureldap.LDAPFilterMatchAll,
                 attributes=[],
                 ):
        LDAPOperation.__init__(self, client)
        r=pureldap.LDAPSearchRequest(baseObject=baseObject,
                                     scope=scope,
                                     derefAliases=derefAliases,
                                     sizeLimit=sizeLimit,
                                     timeLimit=timeLimit,
                                     typesOnly=typesOnly,
                                     filter=filter,
                                     attributes=attributes)
        self.client.queue(r, self.handle_msg)

    def handle_msg(self, msg):
        if isinstance(msg, pureldap.LDAPSearchResultDone):
            assert msg.referral==None #TODO
            if msg.resultCode==0: #TODO ldap.errors.success
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

class LDAPModifyAttributes(LDAPOperation):
    def __init__(self,
                 client,
                 object,
                 modification):
        """
        Request modification of LDAP attributes.

        object is a string represetation of the object DN.

        modification is a list of LDAPModifications
        """

        LDAPOperation.__init__(self, client)
        r=pureldap.LDAPModifyRequest(object=object,
                                     modification=modification)
        self.client.queue(r, self.handle_msg)

    def handle_msg(self, msg):
        assert isinstance(msg, pureldap.LDAPModifyResponse)
        assert msg.referral==None #TODO
        if msg.resultCode==0: #TODO ldap.errors.success
            assert msg.matchedDN==''
            self.handle_success()
        else:
            self.handle_fail(msg.resultCode,
                             msg.errorMessage)
            return 1
            
    def handle_success(self):
        pass

    def handle_fail(self, resultCode, errorMessage):
        pass


class LDAPDeleteAttributes(LDAPModifyAttributes):
    def __init__(self,
                 client,
                 object,
                 vals):
        """
        Request deletion of LDAP attributes.

        object is a string represetation of the object DN.

        vals is a list of (type, vals) pairs, where

        type is a string

        vals is a list of values to remove. Additionally, vals can be
        an empty list or can be left out in order to remove all
        values. """

        mod = pureldap.LDAPModification_delete(vals=vals)
        LDAPModifyAttributes.__init__(self, client,
                                      object, [mod])
