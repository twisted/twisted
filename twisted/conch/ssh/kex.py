# -*- test-case-name: twisted.conch.test.test_transport -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
SSH key exchange handling.

Maintainer: Paul Swartz
"""

from zope.interface import Attribute, implementer, Interface

from twisted.conch import error


class _IAlgorithm(Interface):
    """
    An L{_IAlgorithm} describes a key exchange algorithm.

    Note that primes are not present for key exchange algorithms that do not
    have a fixed group (C{fixedGroup=False}).  In these cases, a prime /
    generator group should be chosen at run time based on the requested
    size.  See RFC 4419.
    """

    preference = Attribute(
        "An C{int} giving the preference of the algorithm when negotiating "
        "key exchange.  Algorithms with lower precedence values are more "
        "preferred.")

    fixedGroup = Attribute(
        "A C{bool} which is True if the key exchange algorithm prime / "
        "generator group is predefined.  Fixed groups are handled "
        "differently within transport logic.  Key exchange algorithms with "
        "a fixed group must define prime and generator numbers.")

    prime = Attribute(
        "A C{long} giving the prime number used in Diffie-Hellman key "
        "exchange, or C{None} if not applicable.")

    generator = Attribute(
        "A C{long} giving the generator number used in Diffie-Hellman key "
        "exchange, or C{None} if not applicable.  (This is not related to "
        "Python generator functions.)")



@implementer(_IAlgorithm)
class _DHGroupExchangeSHA1(object):
    """
    Diffie-Hellman Group and Key Exchange with SHA-1 as HASH.  Defined in
    RFC 4419, 4.1.
    """

    preference = 1
    fixedGroup = False



@implementer(_IAlgorithm)
class _DHGroup1SHA1(object):
    """
    Diffie-Hellman key exchange with SHA-1 as HASH, and Oakley Group 2
    (1024-bit MODP Group).  Defined in RFC 4253, 8.1.
    """

    preference = 2
    fixedGroup = True
    # Diffie-Hellman primes from Oakley Group 2 (RFC 2409, 6.2).
    prime = long('17976931348623159077083915679378745319786029604875601170644'
        '44236841971802161585193689478337958649255415021805654859805036464405'
        '48199239100050792877003355816639229553136239076508735759914822574862'
        '57500742530207744771258955095793777842444242661733472762929938766870'
        '9205606050270810842907692932019128194467627007L')
    generator = 2L



@implementer(_IAlgorithm)
class _DHGroup14SHA1(object):
    """
    Diffie-Hellman key exchange with SHA-1 as HASH and Oakley Group 14
    (2048-bit MODP Group).  Defined in RFC 4253, 8.2.
    """

    preference = 3
    fixedGroup = True
    # Diffie-Hellman primes from Oakley Group 14 (RFC 3526, 3).
    prime = long('32317006071311007300338913926423828248817941241140239112842'
        '00975140074170663435422261968941736356934711790173790970419175460587'
        '32091950288537589861856221532121754125149017745202702357960782362488'
        '84246189477587641105928646099411723245426622522193230540919037680524'
        '23551912567971587011700105805587765103886184728025797605490356973256'
        '15261670813393617995413364765591603683178967290731783845896806396719'
        '00977202194168647225871031411336429319536193471636533209717077448227'
        '98858856536920864529663607725026895550592836275112117409697299806841'
        '05543595848665832916421362182310789909994486524682624169720359118525'
        '07045361090559L')
    generator = 2L



_kexAlgorithms = {
    "diffie-hellman-group-exchange-sha1": _DHGroupExchangeSHA1(),
    "diffie-hellman-group1-sha1": _DHGroup1SHA1(),
    "diffie-hellman-group14-sha1": _DHGroup14SHA1(),
    }



def _getKex(kexAlgo):
    """
    Get a description of a named key exchange algorithm.

    @type kexAlgo: C{str}
    @param kexAlgo: The key exchange algorithm name.

    @rtype: L{_IAlgorithm}
    @return: A description of the key exchange algorithm named by C{kexAlgo}.

    @raises ConchError: if the key exchange algorithm is not found.
    """
    if kexAlgo not in _kexAlgorithms:
        raise error.ConchError(
            "Unsupported key exchange algorithm: %s" % (kexAlgo,))
    return _kexAlgorithms[kexAlgo]



def isFixedGroup(kexAlgo):
    """
    Returns C{True} if C{kexAlgo} has a fixed prime / generator group.  Used
    to determine the correct key exchange logic to perform.

    @type kexAlgo: C{str}
    @param kexAlgo: The key exchange algorithm name.

    @rtype: C{bool}
    @return: C{True} if C{kexAlgo} has a fixed prime / generator group,
        otherwise C{False}.
    """
    return _getKex(kexAlgo).fixedGroup



def getDHPrime(kexAlgo):
    """
    Get the prime and generator to use in key exchange.

    @type kexAlgo: C{str}
    @param kexAlgo: The key exchange algorithm name.

    @rtype: C{tuple}
    @return: A C{tuple} containing C{long} generator and C{long} prime.
    """
    kex = _getKex(kexAlgo)
    return kex.generator, kex.prime



def getSupportedKeyExchanges():
    """
    Get a list of supported key exchange algorithm names in order of
    preference.

    @rtype: C{list} of L{str}
    @return: A C{list} of supported key exchange algorithm names.
    """
    return sorted(
        _kexAlgorithms,
        key = lambda kexAlgo: _kexAlgorithms[kexAlgo].preference)
