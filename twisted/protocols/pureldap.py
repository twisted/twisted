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

class LDAPString(BEROctetString):
    pass

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

class LDAPAttributeDescription(BEROctetString):
    pass

class LDAPAttributeValueAssertion(BERSequence):
    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
        self.attributeDesc=self.data[0]
        self.assertionValue=self.data[1]
        assert len(self.data)==2
        
    def __init__(self, attributeDesc=None, assertionValue=None,
                 encoded=None, berdecoder=None):
        BERSequence.__init__(self, value=[])
        if attributeDesc!=None:
            assert encoded==None
            self.attributeDesc=attributeDesc
            self.assertionValue=assertionValue
        elif encoded!=None:
            assert attributeDesc==None
            assert assertionValue==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(BERSequence([self.attributeDesc,
                                self.assertionValue],
                               tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(attributeDesc=%s, assertionValue=%s)"\
                   %(repr(self.attributeDesc), repr(self.assertionValue))
        else:
            return self.__class__.__name__+"(attributeDesc=%s, assertionValue=%s, tag=%d)"\
                   %(repr(self.attributeDesc), repr(self.assertionValue), self.tag)


class LDAPFilter:
    def decode(self, encoded, berdecoder):
        self.value=ber2object(LDAPBERDecoderContext_Filter(fallback=berdecoder, inherit=berdecoder), encoded)
        assert self.value

    def __init__(self, encoded=None, berdecoder=None):
        if encoded!=None:
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(self.value)

class LDAPFilterSet(BERSet):
    pass

class LDAPFilter_and(LDAPFilterSet):
    tag = CLASS_CONTEXT|0x00
    pass

class LDAPFilter_or(LDAPFilterSet):
    tag = CLASS_CONTEXT|0x01
    pass

class LDAPFilter_not(LDAPFilter):
    tag = CLASS_CONTEXT|0x02
    pass

class LDAPFilter_equalityMatch(LDAPAttributeValueAssertion):
    tag = CLASS_CONTEXT|0x03
    pass

class LDAPFilter_substrings_initial(LDAPString):
    tag = CLASS_CONTEXT|0x00
    pass

class LDAPFilter_substrings_any(LDAPString):
    tag = CLASS_CONTEXT|0x01
    pass

class LDAPFilter_substrings_final(LDAPString):
    tag = CLASS_CONTEXT|0x02
    pass

class LDAPBERDecoderContext_Filter_substrings(BERDecoderContext):
    Identities = {
        LDAPFilter_substrings_initial.tag: LDAPFilter_substrings_initial,
        LDAPFilter_substrings_any.tag: LDAPFilter_substrings_any,
        LDAPFilter_substrings_final.tag: LDAPFilter_substrings_final,
        }

class LDAPFilter_substrings(BERSequence):
    tag = CLASS_CONTEXT|0x04

    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encded, LDAPBERDecoderContext_Filter_substrings(fallback=berdecoder))
        assert len(self.data)==2
        self.type=self.data[0]
        assert len(self.data[1])>=1
        self.substrings=self.data[1]

    def __init__(self, type=None, substrings=None, encoded=None, berdecoder=None, tag=None):
        BERSequence.__init__(self, value=[], tag=tag)
        if type!=None and substrings!=None:
            assert encoded==None
            self.type=type
            self.substrings=substrings
        elif encoded!=None:
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(BERSequence([
            LDAPString(self.type),
            BERSequence(self.substrings)], tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__\
                   +"(type=%s, substrings=%s)"\
                   %(repr(self.type), repr(self.substrings))
        else:
            return self.__class__.__name__\
                   +"(type=%s, substrings=%s, tag=%d)"\
                   %(repr(self.type), repr(self.substrings), self.tag)


class LDAPFilter_greaterOrEqual(LDAPAttributeValueAssertion):
    tag = CLASS_CONTEXT|0x05
    pass

class LDAPFilter_lessOrEqual(LDAPAttributeValueAssertion):
    tag = CLASS_CONTEXT|0x06
    pass

class LDAPFilter_present(LDAPAttributeDescription):
    tag = CLASS_CONTEXT|0x07
    pass

class LDAPFilter_approxMatch(LDAPAttributeValueAssertion):
    tag = CLASS_CONTEXT|0x08
    pass

class LDAPMatchingRuleId(LDAPString):
    pass

class LDAPAssertionValue(BEROctetString):
    pass

class LDAPMatchingRuleAssertion_matchingRule(LDAPMatchingRuleId):
    tag = CLASS_CONTEXT|0x01
    pass

class LDAPMatchingRuleAssertion_type(LDAPAttributeDescription):
    tag = CLASS_CONTEXT|0x02
    pass

class LDAPMatchingRuleAssertion_matchValue(LDAPAssertionValue):
    tag = CLASS_CONTEXT|0x03
    pass

class LDAPMatchingRuleAssertion_dnAttributes(BERBoolean):
    tag = CLASS_CONTEXT|0x04
    pass

class LDAPBERDecoderContext_MatchingRuleAssertion(BERDecoderContext):
    Identities = {
        LDAPMatchingRuleAssertion_matchingRule.tag: LDAPMatchingRuleAssertion_matchingRule,
        LDAPMatchingRuleAssertion_type.tag: LDAPMatchingRuleAssertion_type,
        LDAPMatchingRuleAssertion_matchValue.tag: LDAPMatchingRuleAssertion_matchValue,
        LDAPMatchingRuleAssertion_dnAttributes.tag: LDAPMatchingRuleAssertion_dnAttributes,
        }

class LDAPMatchingRuleAssertion(BERSequence):
    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, LDAPBERDecoderContext_MatchingRuleAssertion(fallback=berdecoder, inherit=berdecoder))
        assert 1<=len(self.data)<=4
        self.matchingRule=None
        self.type=None
        self.matchValue=None
        self.dnAttributes=None
        if isinstance(self.data[0], LDAPMatchingRuleAssertion_matchingRule):
            self.matchingRule=self.data[0]
            del self.data[0]
        if len(self.data)>1 \
           and isinstance(self.data[0], LDAPMatchingRuleAssertion_type):
            self.type=self.data[0]
            del self.data[0]
        if len(self.data)>1 \
           and isinstance(self.data[0], LDAPMatchingRuleAssertion_matchValue):
            self.matchValue=self.data[0]
            del self.data[0]
        if len(self.data)>1 \
           and isinstance(self.data[0], LDAPMatchingRuleAssertion_dnAttributes):
            self.dnAttributes=self.data[0]
            del self.data[0]
        assert self.matchValue
        if not self.dnAttributes:
            self.dnAttributes=None

    def __init__(self, matchingRule=None, type=None,
                 matchValue=None, dnAttributes=None,
                 encoded=None, berdecoder=None, tag=None):
        BERSequence.__init__(self, value=[])
        if matchValue!=None:
            assert encoded==None
            self.matchingRule=matchingRule
            self.type=type
            self.matchValue=matchValue
            self.dnAttributes=dnAttributes
            if not self.dnAttributes:
                self.dnAttributes=None
        elif encoded!=None:
            assert matchingRule==None
            assert type==None
            assert matchValue==None
            assert dnAttributes==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return str(BERSequence(
            filter(lambda x: x!=None, [self.matchingRule, self.type, self.matchValue, self.dnAttributes]), tag=self.tag))

class LDAPFilter_extensibleMatch(LDAPMatchingRuleAssertion):
    tag = CLASS_CONTEXT|0x09
    pass


class LDAPBERDecoderContext_Filter(BERDecoderContext):
    Identities = {
        LDAPFilter_and.tag: LDAPFilter_and,
        LDAPFilter_or.tag: LDAPFilter_or,
        LDAPFilter_not.tag: LDAPFilter_not,
        LDAPFilter_equalityMatch.tag: LDAPFilter_equalityMatch,
        LDAPFilter_substrings.tag: LDAPFilter_substrings,
        LDAPFilter_greaterOrEqual.tag: LDAPFilter_greaterOrEqual,
        LDAPFilter_lessOrEqual.tag: LDAPFilter_lessOrEqual,
        LDAPFilter_present.tag: LDAPFilter_present,
        LDAPFilter_approxMatch.tag: LDAPFilter_approxMatch,
        LDAPFilter_extensibleMatch.tag: LDAPFilter_extensibleMatch,
        }

LDAP_SCOPE_baseObject=0
LDAP_SCOPE_singleLevel=1
LDAP_SCOPE_wholeSubtree=2

LDAP_DEREF_neverDerefAliases=0
LDAP_DEREF_derefInSearching=1
LDAP_DEREF_derefFindingBaseObj=2
LDAP_DEREF_derefAlways=3

LDAPFilterMatchAll = LDAPFilter_present('objectclass')

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


class LDAPModification(BERSequence):
    op = None

    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder)
        self.op=self.data[0].value
        self.vals=map(lambda x: x.value, self.data[1:])

    def __init__(self, vals=None, op=None, encoded=None, berdecoder=None, tag=None):
        BERSequence.__init__(self, [])
        if encoded!=None:
            assert vals==None
            assert op==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        elif vals!=None:
            self.vals=vals
            if op:
                self.op=op
        else:
            raise "You must give either value or encoded"


    def __str__(self):
        assert self.op!=None
        r=[]
        for x in self.vals:
            type=x[0]
            try:
                v=x[1]
            except IndexError:
                v=()
            r.append(BERSequence([LDAPAttributeDescription(type), BERSet(map(LDAPString, v))]))
        return str(BERSequence([BEREnumerated(self.op)]+r))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(vals=%s, op=%d)"\
                   %(repr(self.vals), self.op)
        else:
            return self.__class__.__name__+"(vals=%s, op=%d, tag=%d)" \
                   %(repr(self.vals), self.op, self.tag)



class LDAPModification_add(LDAPModification):
    op = 0

class LDAPModification_delete(LDAPModification):
    op = 1

class LDAPModification_replace(LDAPModification):
    op = 2

class LDAPBERDecoderContext_LDAPMessage(BERDecoderContext):
    Identities = {
        BERSequence.tag: LDAPMessage
        }

class LDAPModifyRequest(LDAPProtocolRequest, BERSequence):
    tag=CLASS_APPLICATION|0x06

    def decode(self, encoded, berdecoder):
        BERSequence.decode(self, encoded, berdecoder) #TODO use special decoder with LDAPModification_*.
        self.object=self.data[0].value
        self.modification=self.data[1]

    def __init__(self, object=None, modification=None, encoded=None, berdecoder=None, tag=None):
        """Initialize the object

l=LDAPModifyRequest(object='cn=foo,dc=example,dc=com',
                    modification=(LDAPModification_add('attr1', ('value1', 'value2')),
                                 (LDAPModification_delete('attr2'))))
"""

        LDAPProtocolRequest.__init__(self)
        BERSequence.__init__(self, [])
        if encoded!=None:
            assert object==None
            assert modification==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            self.object=object
            self.modification=modification

    def __str__(self):
        return str(BERSequence([
            LDAPString(self.object),
            BERSequence(self.modification)
            ], tag=self.tag))

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(object=%s, modification=%s)"\
                   %(repr(self.object), repr(self.modification))
        else:
            return self.__class__.__name__+"(object=%s, modification=%s, tag=%d)" \
                   %(repr(self.object), repr(self.modification), self.tag)


class LDAPModifyResponse(LDAPResult):
    tag = CLASS_APPLICATION|0x07


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
#    needs_answer=0
#    pass




class LDAPBERDecoderContext(BERDecoderContext):
    Identities = {
        LDAPBindResponse.tag: LDAPBindResponse,
        LDAPSearchResultEntry.tag: LDAPSearchResultEntry,
        LDAPSearchResultDone.tag: LDAPSearchResultDone,
        LDAPReferral.tag: LDAPReferral,
        LDAPModifyRequest.tag: LDAPModifyRequest,
        LDAPModifyResponse.tag: LDAPModifyResponse,
    }


class LDAPBERDecoderContext_LDAPMessage(BERDecoderContext):
    Identities = {
        BERSequence.tag: LDAPMessage
        }
