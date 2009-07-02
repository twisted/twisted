# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A basic ASN.1 parser.  Deprecated since Twisted 9.0 in favor of PyASN1.

Maintainer: Paul Swartz
"""

import itertools
from pyasn1.type import univ
from pyasn1.codec.ber import decoder, encoder
from twisted.python.deprecate import deprecated
from twisted.python import versions

Twisted9point0 = versions.Version('Twisted', 9, 0, 0)

def parse(data):
    return decoder.decode(data)[0]

parse = deprecated(Twisted9point0)(parse)


def pack(data):
    asn1Sequence = univ.Sequence()
    for index, value in itertools.izip(itertools.count(), data):
        try:
            valueAsInteger = univ.Integer(value)
        except TypeError:
            raise ValueError("cannot pack %r" % (value,))
        asn1Sequence.setComponentByPosition(index, univ.Integer(value))
    return encoder.encode(asn1Sequence)

pack = deprecated(Twisted9point0)(pack)
