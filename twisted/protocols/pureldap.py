"""LDAP protocol handling"""

import sys
import os
from pureber import *

next_ldap_message_id=1
def alloc_ldap_message_id():
    global next_ldap_message_id
    r=next_ldap_message_id
    next_ldap_message_id=next_ldap_message_id+1
    return r

class LDAPMessage(BERSequence):
    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
        self.id=self.data[0].value
        self.value=self.data[1]
        assert self.data[2:]==[]

    def __init__(self, value=None, encoded=None, id=None, berdecoder=None, tag=None):
        BERSequence.__init__(self, value=[], encoded=None, tag=tag)
        if value!=None:
            assert encoded==None
            self.id=id
            if self.id==None:
                self.id=alloc_ldap_message_id()
            self.value=value
        elif encoded!=None:
            assert value==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(BERSequence([BERInteger(self.id), self.value]))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(id=%d, value=%s)"\
                   %(self.id, repr(self.value))
        else:
            return self.__class__.__name__+"(id=%d, value=%s, tag=%d)" \
                   %(self.id, repr(self.value), self.tag)

class LDAPProtocolOp:
    def __init__(self):
        pass

    def __str__(self):
        raise

class LDAPProtocolRequest(LDAPProtocolOp):
    needs_answer=1
    pass

class LDAPProtocolResponse(LDAPProtocolOp):
    pass

class LDAPBindRequest(LDAPProtocolRequest, BERSequence):
    tag=CLASS_APPLICATION|0x00

    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
        self.version=self.data[0].value
        self.dn=self.data[1].value
        self.auth=self.data[2].value

    def __init__(self, version=None, dn=None, auth=None, encoded=None, berdecoder=None, tag=None):
        LDAPProtocolRequest.__init__(self)
        BERSequence.__init__(self, [])
        if encoded!=None:
            assert version==None
            assert dn==None
            assert auth==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            self.version=version
            if self.version==None:
                self.version=3
            self.dn=dn
            if self.dn==None:
                self.dn=''
            self.auth=auth
            if self.auth==None:
                self.auth=''

    def __str__(self):
        return str(BERSequence([
            BERInteger(self.version),
            BEROctetString(self.dn),
            BEROctetString(self.auth, tag=CLASS_CONTEXT|0),
            ], tag=self.tag))


class LDAPReferral(BERSequence):
    tag = CLASS_CONTEXT | 0x03

class LDAPResult(LDAPProtocolResponse, BERSequence):
    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
        self.resultCode=self.data[0].value
        self.matchedDN=self.data[1].value
        self.errorMessage=self.data[2].value
        del self.data[0:3]
        try:
            x=self.data[0]
        except IndexError:
            self.referral=None
        else:
            if isinstance(x, LDAPReferral):
                #TODO support referrals
                #self.referral=self.data[0]
                self.referral=None
                del self.data[0]
            else:
                self.referral=None

    def __init__(self, resultCode=None, matchedDN=None, errorMessage=None, referral=None, serverSaslCreds=None, encoded=None, berdecoder=None):
        LDAPProtocolResponse.__init__(self)
        BERSequence.__init__(self, value=[])
        if resultCode!=None and matchedDN!=None and errorMessage!=None:
            assert encoded==None
            self.resultCode=resultCode
            self.matchedDN=matchedDN
            self.errorMessage=errorMessage
            self.referral=referral
            self.serverSaslCreds=serverSaslCreds
        elif encoded!=None:
            assert resultCode==None
            assert matchedDN==None
            assert errorMessage==None
            assert referral==None
            assert serverSaslCreds==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        assert self.referral==None #TODO
        return str(BERSequence([
            BEREnumerated(self.resultCode),
            BEROctetString(str(BEROctetString(self.matchedDN))),
            BEROctetString(self.errorMessage),
            #TODO referral [3] Referral OPTIONAL
            ], tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__ \
                   +("(resultCode=%d, matchedDN=%s, " \
                     +"errorMessage=%s, referral=%s)") \
                     %(self.resultCode, repr(str(self.matchedDN)), repr(str(self.errorMessage)), repr(self.referral))
        else:
            return self.__class__.__name__ \
                   +"(resultCode=%d, matchedDN=%s, " \
                   +"errorMessage=%s, referral=%s, " \
                   +"tag=%d)" \
                   %(self.resultCode, repr(str(self.matchedDN)), repr(str(self.errorMessage)), self.referral, self.tag)

class LDAPBindResponse_serverSaslCreds(BERSequence):
    tag = CLASS_CONTEXT|0x03

    pass

class LDAPBERDecoderContext_BindResponse(BERDecoderContext):
    Identities = {
        LDAPBindResponse_serverSaslCreds.tag: LDAPBindResponse_serverSaslCreds,
        }

class LDAPBindResponse(LDAPResult):
    tag=CLASS_APPLICATION|0x01

    def decode(self, encoded, berdecoder):
        LDAPResult.decode(self, encoded, LDAPBERDecoderContext_BindResponse(fallback=berdecoder))
        try:
            if isinstance(self.data[0], LDAPBindResponse_serverSaslCreds):
                self.serverSaslCreds=self.data[0]
                del self.data[0]
            else:
                self.serverSaslCreds=None
        except IndexError:
            self.serverSaslCreds=None

    def __init__(self, resultCode=None, matchedDN=None, errorMessage=None, referral=None, serverSaslCreds=None, encoded=None, berdecoder=None):
        assert serverSaslCreds==None #TODO
        LDAPResult.__init__(self, resultCode=resultCode, matchedDN=matchedDN, errorMessage=errorMessage, referral=referral, encoded=encoded, berdecoder=berdecoder)

    def __str__(self):
        assert self.serverSaslCreds==None #TODO
        return LDAPResult.__str__(self)

    def __repr__(self):
        assert self.serverSaslCreds==None #TODO
        return LDAPResult.__repr__(self)

class LDAPUnbindRequest(LDAPProtocolRequest):
    tag=CLASS_APPLICATION|0x02
    needs_answer=0

    def __init__(self, berdecoder=None):
        LDAPProtocolRequest.__init__(self)

    def __str__(self):
        return str(BERNull(tag=self.tag))

class LDAPAttributeValueAssertion:
    def __init__(self, attr, asser=None):
        self.attr=attr
        self.asser=asser

    def __str__(self):
        r=str(BEROctetString(self.attr, tag=0x87))
        if self.asser!=None:
            r=r+str(BEROctetString(self.asser))
        return r

LDAP_SCOPE_baseObject=0
LDAP_SCOPE_singleLevel=1
LDAP_SCOPE_wholeSubtree=2

LDAP_DEREF_neverDerefAliases=0
LDAP_DEREF_derefInSearching=1
LDAP_DEREF_derefFindingBaseObj=2
LDAP_DEREF_derefAlways=3

LDAPFilterMatchAll = LDAPAttributeValueAssertion('objectclass')

"""
Filter ::= CHOICE {
and             [0] SET OF Filter,
or              [1] SET OF Filter,
not             [2] Filter,
equalityMatch   [3] AttributeValueAssertion,
substrings      [4] SubstringFilter,
greaterOrEqual  [5] AttributeValueAssertion,
lessOrEqual     [6] AttributeValueAssertion,
present         [7] AttributeDescription,
approxMatch     [8] AttributeValueAssertion,
extensibleMatch [9] MatchingRuleAssertion }
"""

class LDAPSearchRequest(LDAPProtocolRequest):
    tag=CLASS_APPLICATION|0x03

    #TODO decode

    def __init__(self,
                 baseObject='',
                 scope=LDAP_SCOPE_wholeSubtree,
                 derefAliases=LDAP_DEREF_neverDerefAliases,
                 sizeLimit=0,
                 timeLimit=0,
                 typesOnly=0,
                 filter=LDAPFilterMatchAll,
                 attributes=[], #TODO AttributeDescriptionList
                 ):
        LDAPProtocolRequest.__init__(self)
        self.baseObject=baseObject
        self.scope=scope
        self.derefAliases=derefAliases
        self.sizeLimit=sizeLimit
        self.timeLimit=timeLimit
        self.typesOnly=typesOnly
        self.filter=filter
        self.attributes=attributes

    def __str__(self):
        return str(BERSequence([
            BEROctetString(self.baseObject),
            BEREnumerated(self.scope),
            BEREnumerated(self.derefAliases),
            BERInteger(self.sizeLimit),
            BERInteger(self.timeLimit),
            BERBoolean(self.typesOnly),
            self.filter,
            BERSequenceOf(map(BEROctetString, self.attributes)),
            ], tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__\
                   +("(baseObject=%s, scope=%s, derefAliases=%s, " \
                     +"sizeLimit=%s, timeLimit=%s, typesOnly=%s, " \
                     "filter=%s, attributes=%s)") \
                     %(repr(self.baseObject), self.scope,
                       self.derefAliases, self.sizeLimit,
                       self.timeLimit, self.typesOnly,
                       repr(self.filter), self.attributes)
        
        else:
            return self.__class__.__name__\
                   +("(baseObject=%s, scope=%s, derefAliases=%s, " \
                     +"sizeLimit=%s, timeLimit=%s, typesOnly=%s, " \
                     "filter=%s, attributes=%s, tag=%d)") \
                     %(repr(self.baseObject), self.scope,
                       self.derefAliases, self.sizeLimit,
                       self.timeLimit, self.typesOnly,
                       self.filter, self.attributes, self.tag)

class LDAPSearchResultEntry(LDAPProtocolResponse, BERSequence):
    tag=CLASS_APPLICATION|0x04

    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
	self.objectName=self.data[0].value
        self.attributes=[]
        for attr, li in self.data[1].data:
            self.attributes.append((attr.value, map(lambda x: x.value, li)))

    def __init__(self, objectName=None, attributes=None, encoded=None, berdecoder=None):
        LDAPProtocolResponse.__init__(self)
        BERSequence.__init__(self, [])
        if objectName!=None and attributes!=None:
            assert encoded==None
            self.objectName=objectName
            self.attributes=attributes
        elif encoded!=None:
            assert objectName==None
            assert attributes==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(BERSequence([
            BEROctetString(self.objectName),
            BERSequence(map(lambda (attr,li):
                            BERSequence([BEROctetString(attr),
                                         BERSet(map(BEROctetString,
                                                    li))]),
                            self.attributes)),
            ], tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__\
                   +"(objectName=%s, attributes=%s"\
                   %(repr(str(self.objectName)),
                     repr(map(lambda (a,l):
                              (str(a),
                               map(lambda i, l=l: str(i), l)),
                              self.attributes)))
        else:
            return self.__class__.__name__\
                   +"(objectName=%s, attributes=%s, tag=%d"\
                   %(repr(str(self.objectName)),
                     repr(map(lambda (a,l):
                              (str(a),
                               map(lambda i, l=l: str(i), l)),
                              self.attributes)),
                     self.tag)


class LDAPSearchResultDone(LDAPResult):
    tag=CLASS_APPLICATION|0x05

    pass


#class LDAPModifyResponse(LDAPProtocolResponse):
#    tag = 0x06
#    pass
#class LDAPAddResponse(LDAPProtocolResponse):
#    tag = 0x08
#    pass
#class LDAPDelResponse(LDAPProtocolResponse):
#    tag = 0x10
#    pass
#class LDAPModifyRDNResponse(LDAPProtocolResponse):
#    tag = 0x12
#    pass
#class LDAPCompareResponse(LDAPProtocolResponse):
#    tag = 0x14
#    pass
#class LDAPModifyRequest(LDAPProtocolRequest):
#    tag = 0x05
#    pass
#class LDAPAddRequest(LDAPProtocolRequest):
#    tag = 0x07
#    pass
#class LDAPDelRequest(LDAPProtocolRequest):
#    tag = 0x09
#    pass
#class LDAPModifyRDNRequest(LDAPProtocolRequest):
#    tag = 0x11
#    pass
#class LDAPCompareRequest(LDAPProtocolRequest):
#    tag = 0x13
#    pass
#class LDAPAbandonRequest(LDAPProtocolRequest):
#    tag = 0x15
#    needs_answer=1
#    pass




class LDAPBERDecoderContext(BERDecoderContext):
    Identities = {
        LDAPBindResponse.tag: LDAPBindResponse,
        LDAPSearchResultEntry.tag: LDAPSearchResultEntry,
        LDAPSearchResultDone.tag: LDAPSearchResultDone,
        LDAPReferral.tag: LDAPReferral,
    }


class LDAPBERDecoderContext_LDAPMessage(BERDecoderContext):
    Identities = {
        BERSequence.tag: LDAPMessage
        }
