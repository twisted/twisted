"""Pure, simple, BER encoding and decoding"""

import string
from twisted.python.mutablestring import MutableString

# xxxxxxxx
# |/|\.../
# | | |
# | | tag
# | |
# | primitive (0) or structured (1)
# |
# class

CLASS_MASK		= 0xc0
CLASS_UNIVERSAL 	= 0x00
CLASS_APPLICATION 	= 0x40
CLASS_CONTEXT 		= 0x80
CLASS_PRIVATE 		= 0xc0

STRUCTURED_MASK		= 0x20
STRUCTURED 		= 0x20
NOT_STRUCTURED 		= 0x00

TAG_MASK		= 0x1f

# LENGTH
# 0xxxxxxx = 0..127
# 1xxxxxxx = len is stored in the next 0xxxxxxx octets
# indefinite form not supported

import UserList
import UserDict
import types

def berlen2int(m):
    need(m, 1)
    l=ber2int(m[0])
    ll=0
    if l&0x80:
        l=l+128
        ll=l
        need(m, 1+ll)
        l=ber2int(m[1:1+ll], signed=0)
    del m[:1+ll]
    return l

def int2berlen(i):
    assert i>=0
    e=int2ber(i)
    l=len(e)
    assert l>0
    if l==1:
        return e
    else:
        assert l<=127
        le=int2ber(l)
        assert len(le)==1
        assert ord(le[0])&0x80==0
        le0=chr(ord(le[0])|0x80)
        assert ord(le0)&0x80
        return le0+le[1:]+e

def int2ber(i):
    encoded=MutableString()
    while i>127 or i<-128:
        encoded=chr(i%256)+encoded
        i=i>>8
    encoded=chr(i%256)+encoded
    return encoded

def ber2int(e, signed=1):
    need(e, 1)
    v=ord(e[0])
    if v&0x80 and signed:
        v=v-256
    for i in range(1, len(e)):
        v=(v<<8) | ord(e[i])
    return v

class BERBase:
    tag = None

    def identification(self):
        return self.tag
    
    def __init__(self, tag=None):
        if tag!=None:
            self.tag=tag

    def __len__(self):
        return len(str(self))

class BERStructured(BERBase):
    def identification(self):
        return STRUCTURED|self.tag

class BERException(Exception): pass

class BERExceptionInsufficientData(Exception): pass

def need(buf, n):
    d=n-len(buf)
    if d>0:
        raise BERExceptionInsufficientData, d

class BERInteger(BERBase):
    tag = 0x02

    def decode(self, encoded, berdecoder):
        e2=MutableString(encoded)
        need(e2, 2)
        self.tag=ber2int(e2[0], signed=0)&(CLASS_MASK|TAG_MASK)
        del e2[0]
        l=berlen2int(e2)
        assert l>0
        need(e2, l)
        e=e2[:l]
        del e2[:l]
        encoded.set(e2)
        self.value=ber2int(e)

    def __init__(self, value=None, encoded=None, berdecoder=None, tag=None):
        """Create a new BERInteger object.
        Either value or encoded must be given:
        value is an integer, encoded is a MutableString.
        """
        BERBase.__init__(self, tag)
        if value!=None:
            assert encoded==None
            self.value=value
        elif encoded!=None:
            assert value==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"
        
    def __str__(self):
        encoded=int2ber(self.value)
        return chr(self.identification()) \
               +int2berlen(len(encoded)) \
               +encoded

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(value=%d)"%self.value
        else:
            return self.__class__.__name__+"(value=%d, tag=%d)" \
                   %(self.value, self.tag)

class BEROctetString(BERBase):
    tag = 0x04

    def decode(self, encoded, berdecoder):
        e2=MutableString(encoded)
        need(e2, 2)
        self.tag=ber2int(e2[0], signed=0)&(CLASS_MASK|TAG_MASK)
        del e2[0]
        l=berlen2int(e2)
        assert l>=0
        need(e2, l)
        e=e2[:l]
        del e2[:l]
        encoded.set(e2)
        self.value=e

    def __init__(self, value=None, encoded=None, berdecoder=None, tag=None):
        BERBase.__init__(self, tag)
        if value!=None:
            assert encoded==None
            self.value=value
        elif encoded!=None:
            assert value==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        return chr(self.identification()) \
               +int2berlen(len(self.value)) \
               +self.value

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(value=%s)" \
                   %repr(self.value)
        else:
            return self.__class__.__name__ \
                   +"(value=%s, tag=%d)" \
                   %(repr(self.value), self.tag)

class BERNull(BERBase):
    tag = 0x05

    def decode(self, encoded, berdecoder):
        need(encoded, 2)
        self.tag=ber2int(encoded[0], signed=0)&(CLASS_MASK|TAG_MASK)
        assert encoded[1]=='\000'
        del encoded[:2]

    def __init__(self, encoded=None, berdecoder=None, tag=None):
        BERBase.__init__(self, tag)
        if encoded!=None:
            assert berdecoder
            self.decode(encoded, berdecoder)

    def __str__(self):
        return chr(self.identification())+chr(0)

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"()"
        else:
            return self.__class__.__name__+"(tag=%d)"%self.tag

class BERBoolean(BERBase):
    tag = 0x01

    def decode(self, encoded, berdecoder):
        e2=MutableString(encoded)
        need(e2, 2)
        self.tag=ber2int(e2[0], signed=0)&(CLASS_MASK|TAG_MASK)
        del e2[0]
        l=berlen2int(e2)
        assert l>0
        need(e2, l)
        e=e2[:l]
        del e2[:l]
        encoded.set(e2)
        v=ber2int(e)
        if v:
           v=0xFF
        self.value=v

    def __init__(self, value=None, encoded=None, berdecoder=None, tag=None):
        """Create a new BERInteger object.
        Either value or encoded must be given:
        value is an integer, encoded is a MutableString.
        """
        BERBase.__init__(self, tag)
        if value!=None:
            assert encoded==None
            if value:
                value=0xFF 
            self.value=value
        elif encoded!=None:
            assert value==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"
        
    def __str__(self):
        assert self.value==0 or self.value==0xFF
        return chr(self.identification()) \
               +int2berlen(1) \
               +chr(self.value)

    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(value=%d)"%self.value
        else:
            return self.__class__.__name__+"(value=%d, tag=%d)" \
                   %(self.value, self.tag)


class BEREnumerated(BERInteger):
    tag = 0x0a

class BERSequence(BERStructured, UserList.UserList):
    tag = 0x10

    def decode(self, encoded, berdecoder):
        e2=MutableString(encoded)
        need(e2, 2)
        self.tag=ber2int(e2[0], signed=0)&(CLASS_MASK|TAG_MASK)
        del e2[0]
        l=berlen2int(e2)
        need(e2, l)
        content=e2[:l]
        del e2[:l]
        self[:]=[]
        # decode content
        while content:
            n=ber2object(berdecoder, content)
            assert n!=None
            self.append(n)
        encoded.set(e2)

    def __init__(self, value=None, encoded=None, berdecoder=None, tag=None):
        BERStructured.__init__(self, tag)
        UserList.UserList.__init__(self)
        if value!=None:
            assert encoded==None
            self[:]=value
        elif encoded!=None:
            assert value==None
            assert berdecoder
            self.decode(encoded, berdecoder)
        else:
            raise "You must give either value or encoded"

    def __str__(self):
        r=string.join(map(str, self.data), '')
        return chr(self.identification())+int2berlen(len(r))+r
    
    def __repr__(self):
        if self.tag==self.__class__.tag:
            return self.__class__.__name__+"(value=%s)"%repr(self.data)
        else:
            return self.__class__.__name__+"(value=%s, tag=%d)" \
                   %(repr(self.data), self.tag)


class BERSequenceOf(BERSequence):
    pass

class BERSet(BERSequence):
    tag = 0x11
    pass



class BERDecoderContext:
    Identities = {
        BERInteger.tag: BERInteger,
        BEROctetString.tag: BEROctetString,
        BERNull.tag: BERNull,
        BERBoolean.tag: BERBoolean,
        BEREnumerated.tag: BEREnumerated,
        BERSequence.tag: BERSequence,
        BERSet.tag: BERSet,
        }

    def __init__(self, fallback=None, inherit=None):
        self.fallback=fallback
        self.inherit_context=inherit

    def lookup_id(self, id):
        try:
            return self.Identities[id]
        except KeyError:
            if self.fallback:
                return self.fallback.lookup_id(id)
            else:
                return None

    def inherit(self):
        return self.inherit_context or self

def ber2object(context, m):
    """ber2object(mutablestring) -> berobject
    Modifies mutablestring to remove decoded part.
    May give None
    """
    while m:
        need(m, 1)
        i=ber2int(m[0], signed=0)&(CLASS_MASK|TAG_MASK)
        berclass=context.lookup_id(i)
        if berclass:
            inh=context.inherit()
            assert inh
            return berclass(encoded=m, berdecoder=inh)
        else:
            raise "BERDecoderContext %s has no tag 0x%02x"%(context, i)
            tag=ber2int(m[0], signed=0)
            del m[0]
            l=berlen2int(m)
            print "Skipped unknown tag=%d, len=%d"%(tag,l)
            del m[:l]
            return None

#TODO unimplemented classes are below:

#class BERObjectIdentifier(BERBase):
#    tag = 0x06
#    pass

#class BERIA5String(BERBase):
#    tag = 0x16
#    pass

#class BERPrintableString(BERBase):
#    tag = 0x13
#    pass

#class BERT61String(BERBase):
#    tag = 0x14
#    pass

#class BERUTCTime(BERBase):
#    tag = 0x17
#    pass

#class BERBitString(BERBase):
#    tag = 0x03
#    pass

