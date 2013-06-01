# -*- test-case-name: twisted.test.test_sslverify -*-
# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import division, absolute_import

import itertools
from hashlib import md5

from OpenSSL import SSL, crypto

from twisted.python.compat import nativeString, networkString
from twisted.python import _reflectpy3 as reflect, util
from twisted.internet.defer import Deferred
from twisted.internet.error import VerifyError, CertificateError

def _sessionCounter(counter=itertools.count()):
    """
    Private - shared between all OpenSSLCertificateOptions, counts up to
    provide a unique session id for each context.
    """
    return next(counter)



_x509names = {
    'CN': 'commonName',
    'commonName': 'commonName',

    'O': 'organizationName',
    'organizationName': 'organizationName',

    'OU': 'organizationalUnitName',
    'organizationalUnitName': 'organizationalUnitName',

    'L': 'localityName',
    'localityName': 'localityName',

    'ST': 'stateOrProvinceName',
    'stateOrProvinceName': 'stateOrProvinceName',

    'C': 'countryName',
    'countryName': 'countryName',

    'emailAddress': 'emailAddress'}



class DistinguishedName(dict):
    """
    Identify and describe an entity.

    Distinguished names are used to provide a minimal amount of identifying
    information about a certificate issuer or subject.  They are commonly
    created with one or more of the following fields::

        commonName (CN)
        organizationName (O)
        organizationalUnitName (OU)
        localityName (L)
        stateOrProvinceName (ST)
        countryName (C)
        emailAddress

    A L{DistinguishedName} should be constructed using keyword arguments whose
    keys can be any of the field names above (as a native string), and the
    values are either Unicode text which is encodable to ASCII, or C{bytes}
    limited to the ASCII subset. Any fields passed to the constructor will be
    set as attributes, accessable using both their extended name and their
    shortened acronym. The attribute values will be the ASCII-encoded
    bytes. For example::

        >>> dn = DistinguishedName(commonName=b'www.example.com',
                                   C='US')
        >>> dn.C
        b'US'
        >>> dn.countryName
        b'US'
        >>> hasattr(dn, "organizationName")
        False

    L{DistinguishedName} instances can also be used as dictionaries; the keys
    are extended name of the fields::

        >>> dn.keys()
        ['countryName', 'commonName']
        >>> dn['countryName']
        b'US'

    """
    __slots__ = ()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


    def _copyFrom(self, x509name):
        for name in _x509names:
            value = getattr(x509name, name, None)
            if value is not None:
                setattr(self, name, value)


    def _copyInto(self, x509name):
        for k, v in self.items():
            setattr(x509name, k, nativeString(v))


    def __repr__(self):
        return '<DN %s>' % (dict.__repr__(self)[1:-1])


    def __getattr__(self, attr):
        try:
            return self[_x509names[attr]]
        except KeyError:
            raise AttributeError(attr)


    def __setattr__(self, attr, value):
        if attr not in _x509names:
            raise AttributeError("%s is not a valid OpenSSL X509 name field" % (attr,))
        realAttr = _x509names[attr]
        if not isinstance(value, bytes):
            value = value.encode("ascii")
        self[realAttr] = value


    def inspect(self):
        """
        Return a multi-line, human-readable representation of this DN.

        @rtype: C{str}
        """
        l = []
        lablen = 0
        def uniqueValues(mapping):
            return set(mapping.values())
        for k in sorted(uniqueValues(_x509names)):
            label = util.nameToLabel(k)
            lablen = max(len(label), lablen)
            v = getattr(self, k, None)
            if v is not None:
                l.append((label, nativeString(v)))
        lablen += 2
        for n, (label, attr) in enumerate(l):
            l[n] = (label.rjust(lablen)+': '+ attr)
        return '\n'.join(l)

DN = DistinguishedName


class CertBase:
    def __init__(self, original):
        self.original = original

    def _copyName(self, suffix):
        dn = DistinguishedName()
        dn._copyFrom(getattr(self.original, 'get_'+suffix)())
        return dn

    def getSubject(self):
        """
        Retrieve the subject of this certificate.

        @rtype: L{DistinguishedName}
        @return: A copy of the subject of this certificate.
        """
        return self._copyName('subject')



def _handleattrhelper(Class, transport, methodName):
    """
    (private) Helper for L{Certificate.peerFromTransport} and
    L{Certificate.hostFromTransport} which checks for incompatible handle types
    and null certificates and raises the appropriate exception or returns the
    appropriate certificate object.
    """
    method = getattr(transport.getHandle(),
                     "get_%s_certificate" % (methodName,), None)
    if method is None:
        raise CertificateError(
            "non-TLS transport %r did not have %s certificate" % (transport, methodName))
    cert = method()
    if cert is None:
        raise CertificateError(
            "TLS transport %r did not have %s certificate" % (transport, methodName))
    return Class(cert)


class Certificate(CertBase):
    """
    An x509 certificate.
    """
    def __repr__(self):
        return '<%s Subject=%s Issuer=%s>' % (self.__class__.__name__,
                                              self.getSubject().commonName,
                                              self.getIssuer().commonName)

    def __eq__(self, other):
        if isinstance(other, Certificate):
            return self.dump() == other.dump()
        return False


    def __ne__(self, other):
        return not self.__eq__(other)


    def load(Class, requestData, format=crypto.FILETYPE_ASN1, args=()):
        """
        Load a certificate from an ASN.1- or PEM-format string.

        @rtype: C{Class}
        """
        return Class(crypto.load_certificate(format, requestData), *args)
    load = classmethod(load)
    _load = load


    def dumpPEM(self):
        """
        Dump this certificate to a PEM-format data string.

        @rtype: C{str}
        """
        return self.dump(crypto.FILETYPE_PEM)


    def loadPEM(Class, data):
        """
        Load a certificate from a PEM-format data string.

        @rtype: C{Class}
        """
        return Class.load(data, crypto.FILETYPE_PEM)
    loadPEM = classmethod(loadPEM)


    def peerFromTransport(Class, transport):
        """
        Get the certificate for the remote end of the given transport.

        @type: L{ISystemHandle}
        @rtype: C{Class}

        @raise: L{CertificateError}, if the given transport does not have a peer
        certificate.
        """
        return _handleattrhelper(Class, transport, 'peer')
    peerFromTransport = classmethod(peerFromTransport)


    def hostFromTransport(Class, transport):
        """
        Get the certificate for the local end of the given transport.

        @param transport: an L{ISystemHandle} provider; the transport we will

        @rtype: C{Class}

        @raise: L{CertificateError}, if the given transport does not have a host
        certificate.
        """
        return _handleattrhelper(Class, transport, 'host')
    hostFromTransport = classmethod(hostFromTransport)


    def getPublicKey(self):
        """
        Get the public key for this certificate.

        @rtype: L{PublicKey}
        """
        return PublicKey(self.original.get_pubkey())


    def dump(self, format=crypto.FILETYPE_ASN1):
        return crypto.dump_certificate(format, self.original)


    def serialNumber(self):
        """
        Retrieve the serial number of this certificate.

        @rtype: C{int}
        """
        return self.original.get_serial_number()


    def digest(self, method='md5'):
        """
        Return a digest hash of this certificate using the specified hash
        algorithm.

        @param method: One of C{'md5'} or C{'sha'}.
        @rtype: C{str}
        """
        return self.original.digest(method)


    def _inspect(self):
        return '\n'.join(['Certificate For Subject:',
                          self.getSubject().inspect(),
                          '\nIssuer:',
                          self.getIssuer().inspect(),
                          '\nSerial Number: %d' % self.serialNumber(),
                          'Digest: %s' % nativeString(self.digest())])


    def inspect(self):
        """
        Return a multi-line, human-readable representation of this
        Certificate, including information about the subject, issuer, and
        public key.
        """
        return '\n'.join((self._inspect(), self.getPublicKey().inspect()))


    def getIssuer(self):
        """
        Retrieve the issuer of this certificate.

        @rtype: L{DistinguishedName}
        @return: A copy of the issuer of this certificate.
        """
        return self._copyName('issuer')


    def options(self, *authorities):
        raise NotImplementedError('Possible, but doubtful we need this yet')



class CertificateRequest(CertBase):
    """
    An x509 certificate request.

    Certificate requests are given to certificate authorities to be signed and
    returned resulting in an actual certificate.
    """
    def load(Class, requestData, requestFormat=crypto.FILETYPE_ASN1):
        req = crypto.load_certificate_request(requestFormat, requestData)
        dn = DistinguishedName()
        dn._copyFrom(req.get_subject())
        if not req.verify(req.get_pubkey()):
            raise VerifyError("Can't verify that request for %r is self-signed." % (dn,))
        return Class(req)
    load = classmethod(load)


    def dump(self, format=crypto.FILETYPE_ASN1):
        return crypto.dump_certificate_request(format, self.original)



class PrivateCertificate(Certificate):
    """
    An x509 certificate and private key.
    """
    def __repr__(self):
        return Certificate.__repr__(self) + ' with ' + repr(self.privateKey)


    def _setPrivateKey(self, privateKey):
        if not privateKey.matches(self.getPublicKey()):
            raise VerifyError(
                "Certificate public and private keys do not match.")
        self.privateKey = privateKey
        return self


    def newCertificate(self, newCertData, format=crypto.FILETYPE_ASN1):
        """
        Create a new L{PrivateCertificate} from the given certificate data and
        this instance's private key.
        """
        return self.load(newCertData, self.privateKey, format)


    def load(Class, data, privateKey, format=crypto.FILETYPE_ASN1):
        return Class._load(data, format)._setPrivateKey(privateKey)
    load = classmethod(load)


    def inspect(self):
        return '\n'.join([Certificate._inspect(self),
                          self.privateKey.inspect()])


    def dumpPEM(self):
        """
        Dump both public and private parts of a private certificate to
        PEM-format data.
        """
        return self.dump(crypto.FILETYPE_PEM) + self.privateKey.dump(crypto.FILETYPE_PEM)


    def loadPEM(Class, data):
        """
        Load both private and public parts of a private certificate from a
        chunk of PEM-format data.
        """
        return Class.load(data, KeyPair.load(data, crypto.FILETYPE_PEM),
                          crypto.FILETYPE_PEM)
    loadPEM = classmethod(loadPEM)


    def fromCertificateAndKeyPair(Class, certificateInstance, privateKey):
        privcert = Class(certificateInstance.original)
        return privcert._setPrivateKey(privateKey)
    fromCertificateAndKeyPair = classmethod(fromCertificateAndKeyPair)


    def options(self, *authorities):
        options = dict(privateKey=self.privateKey.original,
                       certificate=self.original)
        if authorities:
            options.update(dict(verify=True,
                                requireCertificate=True,
                                caCerts=[auth.original for auth in authorities]))
        return OpenSSLCertificateOptions(**options)


    def certificateRequest(self, format=crypto.FILETYPE_ASN1,
                           digestAlgorithm='md5'):
        return self.privateKey.certificateRequest(
            self.getSubject(),
            format,
            digestAlgorithm)


    def signCertificateRequest(self,
                               requestData,
                               verifyDNCallback,
                               serialNumber,
                               requestFormat=crypto.FILETYPE_ASN1,
                               certificateFormat=crypto.FILETYPE_ASN1):
        issuer = self.getSubject()
        return self.privateKey.signCertificateRequest(
            issuer,
            requestData,
            verifyDNCallback,
            serialNumber,
            requestFormat,
            certificateFormat)


    def signRequestObject(self, certificateRequest, serialNumber,
                          secondsToExpiry=60 * 60 * 24 * 365, # One year
                          digestAlgorithm='md5'):
        return self.privateKey.signRequestObject(self.getSubject(),
                                                 certificateRequest,
                                                 serialNumber,
                                                 secondsToExpiry,
                                                 digestAlgorithm)


class PublicKey:
    def __init__(self, osslpkey):
        self.original = osslpkey
        req1 = crypto.X509Req()
        req1.set_pubkey(osslpkey)
        self._emptyReq = crypto.dump_certificate_request(crypto.FILETYPE_ASN1, req1)


    def matches(self, otherKey):
        return self._emptyReq == otherKey._emptyReq


    # XXX This could be a useful method, but sometimes it triggers a segfault,
    # so we'll steer clear for now.
#     def verifyCertificate(self, certificate):
#         """
#         returns None, or raises a VerifyError exception if the certificate
#         could not be verified.
#         """
#         if not certificate.original.verify(self.original):
#             raise VerifyError("We didn't sign that certificate.")

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.keyHash())


    def keyHash(self):
        """
        MD5 hex digest of signature on an empty certificate request with this
        key.
        """
        return md5(self._emptyReq).hexdigest()


    def inspect(self):
        return 'Public Key with Hash: %s' % (self.keyHash(),)



class KeyPair(PublicKey):

    def load(Class, data, format=crypto.FILETYPE_ASN1):
        return Class(crypto.load_privatekey(format, data))
    load = classmethod(load)


    def dump(self, format=crypto.FILETYPE_ASN1):
        return crypto.dump_privatekey(format, self.original)


    def __getstate__(self):
        return self.dump()


    def __setstate__(self, state):
        self.__init__(crypto.load_privatekey(crypto.FILETYPE_ASN1, state))


    def inspect(self):
        t = self.original.type()
        if t == crypto.TYPE_RSA:
            ts = 'RSA'
        elif t == crypto.TYPE_DSA:
            ts = 'DSA'
        else:
            ts = '(Unknown Type!)'
        L = (self.original.bits(), ts, self.keyHash())
        return '%s-bit %s Key Pair with Hash: %s' % L


    def generate(Class, kind=crypto.TYPE_RSA, size=1024):
        pkey = crypto.PKey()
        pkey.generate_key(kind, size)
        return Class(pkey)


    def newCertificate(self, newCertData, format=crypto.FILETYPE_ASN1):
        return PrivateCertificate.load(newCertData, self, format)
    generate = classmethod(generate)


    def requestObject(self, distinguishedName, digestAlgorithm='md5'):
        req = crypto.X509Req()
        req.set_pubkey(self.original)
        distinguishedName._copyInto(req.get_subject())
        req.sign(self.original, digestAlgorithm)
        return CertificateRequest(req)


    def certificateRequest(self, distinguishedName,
                           format=crypto.FILETYPE_ASN1,
                           digestAlgorithm='md5'):
        """Create a certificate request signed with this key.

        @return: a string, formatted according to the 'format' argument.
        """
        return self.requestObject(distinguishedName, digestAlgorithm).dump(format)


    def signCertificateRequest(self,
                               issuerDistinguishedName,
                               requestData,
                               verifyDNCallback,
                               serialNumber,
                               requestFormat=crypto.FILETYPE_ASN1,
                               certificateFormat=crypto.FILETYPE_ASN1,
                               secondsToExpiry=60 * 60 * 24 * 365, # One year
                               digestAlgorithm='md5'):
        """
        Given a blob of certificate request data and a certificate authority's
        DistinguishedName, return a blob of signed certificate data.

        If verifyDNCallback returns a Deferred, I will return a Deferred which
        fires the data when that Deferred has completed.
        """
        hlreq = CertificateRequest.load(requestData, requestFormat)

        dn = hlreq.getSubject()
        vval = verifyDNCallback(dn)

        def verified(value):
            if not value:
                raise VerifyError("DN callback %r rejected request DN %r" % (verifyDNCallback, dn))
            return self.signRequestObject(issuerDistinguishedName, hlreq,
                                          serialNumber, secondsToExpiry, digestAlgorithm).dump(certificateFormat)

        if isinstance(vval, Deferred):
            return vval.addCallback(verified)
        else:
            return verified(vval)


    def signRequestObject(self,
                          issuerDistinguishedName,
                          requestObject,
                          serialNumber,
                          secondsToExpiry=60 * 60 * 24 * 365, # One year
                          digestAlgorithm='md5'):
        """
        Sign a CertificateRequest instance, returning a Certificate instance.
        """
        req = requestObject.original
        cert = crypto.X509()
        issuerDistinguishedName._copyInto(cert.get_issuer())
        cert.set_subject(req.get_subject())
        cert.set_pubkey(req.get_pubkey())
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(secondsToExpiry)
        cert.set_serial_number(serialNumber)
        cert.sign(self.original, digestAlgorithm)
        return Certificate(cert)


    def selfSignedCert(self, serialNumber, **kw):
        dn = DN(**kw)
        return PrivateCertificate.fromCertificateAndKeyPair(
            self.signRequestObject(dn, self.requestObject(dn), serialNumber),
            self)



class OpenSSLCertificateOptions(object):
    """
    A factory for SSL context objects for both SSL servers and clients.
    """

    # Factory for creating contexts.  Configurable for testability.
    _contextFactory = SSL.Context
    _context = None
    # Older versions of PyOpenSSL didn't provide OP_ALL.  Fudge it here, just in case.
    _OP_ALL = getattr(SSL, 'OP_ALL', 0x0000FFFF)
    # OP_NO_TICKET is not (yet) exposed by PyOpenSSL
    _OP_NO_TICKET = 0x00004000

    method = SSL.TLSv1_METHOD

    def __init__(self,
                 privateKey=None,
                 certificate=None,
                 method=None,
                 verify=False,
                 caCerts=None,
                 verifyDepth=9,
                 requireCertificate=True,
                 verifyOnce=True,
                 enableSingleUseKeys=True,
                 enableSessions=True,
                 fixBrokenPeers=False,
                 enableSessionTickets=False,
                 extraCertChain=None):
        """
        Create an OpenSSL context SSL connection context factory.

        @param privateKey: A PKey object holding the private key.

        @param certificate: An X509 object holding the certificate.

        @param method: The SSL protocol to use, one of SSLv23_METHOD,
        SSLv2_METHOD, SSLv3_METHOD, TLSv1_METHOD.  Defaults to TLSv1_METHOD.

        @param verify: If C{True}, verify certificates received from the peer
            and fail the handshake if verification fails.  Otherwise, allow
            anonymous sessions and sessions with certificates which fail
            validation.  By default this is C{False}.

        @param caCerts: List of certificate authority certificate objects to
            use to verify the peer's certificate.  Only used if verify is
            C{True} and will be ignored otherwise.  Since verify is C{False} by
            default, this is C{None} by default.

        @type caCerts: C{list} of L{OpenSSL.crypto.X509}

        @param verifyDepth: Depth in certificate chain down to which to verify.
        If unspecified, use the underlying default (9).

        @param requireCertificate: If True, do not allow anonymous sessions.

        @param verifyOnce: If True, do not re-verify the certificate
        on session resumption.

        @param enableSingleUseKeys: If True, generate a new key whenever
        ephemeral DH parameters are used to prevent small subgroup attacks.

        @param enableSessions: If True, set a session ID on each context.  This
        allows a shortened handshake to be used when a known client reconnects.

        @param fixBrokenPeers: If True, enable various non-spec protocol fixes
        for broken SSL implementations.  This should be entirely safe,
        according to the OpenSSL documentation, but YMMV.  This option is now
        off by default, because it causes problems with connections between
        peers using OpenSSL 0.9.8a.

        @param enableSessionTickets: If True, enable session ticket extension
        for session resumption per RFC 5077. Note there is no support for
        controlling session tickets. This option is off by default, as some
        server implementations don't correctly process incoming empty session
        ticket extensions in the hello.

        @param extraCertChain: List of certificates that I{complete} your
            verification chain if the certificate authority that signed your
            C{certificate} isn't widely supported.  Do I{not} add
            C{certificate} to it.

        @type extraCertChain: C{list} of L{OpenSSL.crypto.X509}
        """

        if (privateKey is None) != (certificate is None):
            raise ValueError(
                "Specify neither or both of privateKey and certificate")
        self.privateKey = privateKey
        self.certificate = certificate
        if method is not None:
            self.method = method

        if verify and not caCerts:
            raise ValueError("Specify client CA certificate information if and"
                             " only if enabling certificate verification")
        self.verify = verify
        if extraCertChain is not None and None in (privateKey, certificate):
            raise ValueError("A private key and a certificate are required "
                             "when adding a supplemental certificate chain.")
        if extraCertChain is not None:
            self.extraCertChain = extraCertChain
        else:
            self.extraCertChain = []

        self.caCerts = caCerts
        self.verifyDepth = verifyDepth
        self.requireCertificate = requireCertificate
        self.verifyOnce = verifyOnce
        self.enableSingleUseKeys = enableSingleUseKeys
        self.enableSessions = enableSessions
        self.fixBrokenPeers = fixBrokenPeers
        self.enableSessionTickets = enableSessionTickets


    def __getstate__(self):
        d = self.__dict__.copy()
        try:
            del d['_context']
        except KeyError:
            pass
        return d


    def __setstate__(self, state):
        self.__dict__ = state


    def getContext(self):
        """Return a SSL.Context object.
        """
        if self._context is None:
            self._context = self._makeContext()
        return self._context


    def _makeContext(self):
        ctx = self._contextFactory(self.method)
        # Disallow insecure SSLv2. Applies only for SSLv23_METHOD.
        ctx.set_options(SSL.OP_NO_SSLv2)

        if self.certificate is not None and self.privateKey is not None:
            ctx.use_certificate(self.certificate)
            ctx.use_privatekey(self.privateKey)
            for extraCert in self.extraCertChain:
                ctx.add_extra_chain_cert(extraCert)
            # Sanity check
            ctx.check_privatekey()

        verifyFlags = SSL.VERIFY_NONE
        if self.verify:
            verifyFlags = SSL.VERIFY_PEER
            if self.requireCertificate:
                verifyFlags |= SSL.VERIFY_FAIL_IF_NO_PEER_CERT
            if self.verifyOnce:
                verifyFlags |= SSL.VERIFY_CLIENT_ONCE
            if self.caCerts:
                store = ctx.get_cert_store()
                for cert in self.caCerts:
                    store.add_cert(cert)

        # It'd be nice if pyOpenSSL let us pass None here for this behavior (as
        # the underlying OpenSSL API call allows NULL to be passed).  It
        # doesn't, so we'll supply a function which does the same thing.
        def _verifyCallback(conn, cert, errno, depth, preverify_ok):
            return preverify_ok
        ctx.set_verify(verifyFlags, _verifyCallback)

        if self.verifyDepth is not None:
            ctx.set_verify_depth(self.verifyDepth)

        if self.enableSingleUseKeys:
            ctx.set_options(SSL.OP_SINGLE_DH_USE)

        if self.fixBrokenPeers:
            ctx.set_options(self._OP_ALL)

        if self.enableSessions:
            name = "%s-%d" % (reflect.qual(self.__class__), _sessionCounter())
            sessionName = md5(networkString(name)).hexdigest()

            ctx.set_session_id(sessionName)

        if not self.enableSessionTickets:
            ctx.set_options(self._OP_NO_TICKET)

        return ctx
