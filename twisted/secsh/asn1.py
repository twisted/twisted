# really really basic ASN.1 parser, so we can read private keys from SSH
from Crypto.Util import number

def parse(data):
    things = []
    while data:
        t = ord(data[0])
        assert (t & 0xc0) == 0, 'not a universal value: 0x%02x' % t
        #assert t & 0x20, 'not a constructed value: 0x%02x' % t
        if t & 0x20:
            t = t & ~0x20
        l = ord(data[1])
        assert data != 0x80, "shouldn't be an indefinite length"
        if l & 0x80: # long form
            ll = l & 0x7f
            l = number.bytes_to_long(data[2:2+ll])
            s = 2 + ll
        else:
            s = 2
        body, data = data[s:s+l], data[s+l:]
        t = t&(~0x20)
        assert t in (SEQUENCE, INTEGER), 'bad type: 0x%02x' % t
        if t == SEQUENCE:
            things.append(parse(body))
        elif t == INTEGER:
            assert (ord(body[0])&0x80) == 0, "shouldn't have negative number"
            things.append(number.bytes_to_long(body))
    if len(things) == 1:
        return things[0]
    return things
            
INTEGER = 0x02
SEQUENCE = 0x10