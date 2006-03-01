# Copyright 2005 Divmod, Inc.  See LICENSE file for details

import itertools, md5
from OpenSSL import SSL, crypto

from twisted.python import reflect
from twisted.internet.defer import Deferred

# Private - shared between all ServerContextFactories, counts up to
# provide a unique session id for each context
_sessionCounter = itertools.count().next

class _SSLApplicationData(object):
    def __init__(self):
        self.problems = []

class VerifyError(Exception):
    """Could not verify something that was supposed to be signed.
    """

class PeerVerifyError(VerifyError):
    """The peer rejected our verify error.
    """

class OpenSSLVerifyError(VerifyError):

    _errorCodes = {0: ('X509_V_OK', 'ok', 'the operation was successful. >'),
                   2: ('X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT',
                       'unable to get issuer certificate',
                       "the issuer certificate could not be found', 'this occurs if the issuer certificate of an untrusted certificate cannot be found."),
                   3: ('X509_V_ERR_UNABLE_TO_GET_CRL',
                       ' unable to get certificate CRL',
                       'the CRL of a certificate could not be found. Unused.'),
                   4: ('X509_V_ERR_UNABLE_TO_DECRYPT_CERT_SIGNATURE',
                       "unable to decrypt certificate's signature",
                       'the certificate signature could not be decrypted. This means that the actual signature value could not be determined rather than it not match- ing the expected value, this is only meaningful for RSA keys.'),
                   5: ('X509_V_ERR_UNABLE_TO_DECRYPT_CRL_SIGNATURE',
                       "unable to decrypt CRL's signature",
                       "the CRL signature could not be decrypted', 'this means that the actual signature value could not be determined rather than it not matching the expected value. Unused."),
                   6: ('X509_V_ERR_UNABLE_TO_DECODE_ISSUER_PUBLIC_KEY',
                       'unable to decode issuer',
                       'public key the public key in the certificate SubjectPublicKeyInfo could not be read.'),
                   7: ('X509_V_ERR_CERT_SIGNATURE_FAILURE',
                       'certificate signature failure',
                       'the signature of the certificate is invalid.'),
                   8: ('X509_V_ERR_CRL_SIGNATURE_FAILURE',
                       'CRL signature failure',
                       'the signature of the certificate is invalid. Unused.'),
                   9: ('X509_V_ERR_CERT_NOT_YET_VALID',
                       'certificate is not yet valid',
                       "the certificate is not yet valid', 'the notBefore date is after the cur- rent time."),
                   10: ('X509_V_ERR_CERT_HAS_EXPIRED',
                        'certificate has expired',
                        "the certificate has expired', 'that is the notAfter date is before the current time."),
                   11: ('X509_V_ERR_CRL_NOT_YET_VALID',
                        'CRL is not yet valid',
                        'the CRL is not yet valid. Unused.'),
                   12: ('X509_V_ERR_CRL_HAS_EXPIRED',
                        'CRL has expired',
                        'the CRL has expired. Unused.'),
                   13: ('X509_V_ERR_ERROR_IN_CERT_NOT_BEFORE_FIELD',
                        "format error in certificate's",
                        'notBefore field the certificate notBefore field contains an invalid time.'),
                   14: ('X509_V_ERR_ERROR_IN_CERT_NOT_AFTER_FIELD',
                        "format error in certificate's",
                        'notAfter field the certificate notAfter field contains an invalid time.'),
                   15: ('X509_V_ERR_ERROR_IN_CRL_LAST_UPDATE_FIELD',
                        "format error in CRL's lastUpdate field",
                        'the CRL lastUpdate field contains an invalid time. Unused.'),
                   16: ('X509_V_ERR_ERROR_IN_CRL_NEXT_UPDATE_FIELD',
                        "format error in CRL's nextUpdate field",
                        'the CRL nextUpdate field contains an invalid time. Unused.'),
                   17: ('X509_V_ERR_OUT_OF_MEM',
                        'out of memory',
                        'an error occurred trying to allocate memory. This should never happen.'),
                   18: ('X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT',
                        'self signed certificate',
                        'the passed certificate is self signed and the same certificate cannot be found in the list of trusted certificates.'),
                   19: ('X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN',
                        'self signed certificate in certificate chain',
                        'the certificate chain could be built up using the untrusted certificates but the root could not be found locally.'),
                   20: ('X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
                        'unable to get local issuer',
                        'certificate the issuer certificate of a locally looked up certificate could not be found. This normally means the list of trusted certificates is not com- plete.'),
                   21: ('X509_V_ERR_UNABLE_TO_VERIFY_LEAF_SIGNATURE',
                        'unable to verify the first',
                        'certificate no signatures could be verified because the chain contains only one cer- tificate and it is not self signed.'),
                   22: ('X509_V_ERR_CERT_CHAIN_TOO_LONG',
                        'certificate chain too long',
                        'the certificate chain length is greater than the supplied maximum depth. Unused.'),
                   23: ('X509_V_ERR_CERT_REVOKED',
                        'certificate revoked',
                        'the certificate has been revoked. Unused.'),
                   24: ('X509_V_ERR_INVALID_CA',
                        'invalid CA certificate',
                        'a CA certificate is invalid. Either it is not a CA or its extensions are not consistent with the supplied purpose.'),
                   25: ('X509_V_ERR_PATH_LENGTH_EXCEEDED',
                        'path length constraint exceeded',
                        'the basicConstraints pathlength parameter has been exceeded.'),
                   26: ('X509_V_ERR_INVALID_PURPOSE',
                        'unsupported certificate purpose',
                        'the supplied certificate cannot be used for the specified purpose.'),
                   27: ('X509_V_ERR_CERT_UNTRUSTED',
                        'certificate not trusted',
                        'the root CA is not marked as trusted for the specified purpose.'),
                   28: ('X509_V_ERR_CERT_REJECTED',
                        'certificate rejected',
                        'the root CA is marked to reject the specified purpose.'),
                   29: ('X509_V_ERR_SUBJECT_ISSUER_MISMATCH',
                        'subject issuer mismatch',
                        'the current candidate issuer certificate was rejected because its sub- ject name did not match the issuer name of the current certificate. Only displayed when the -issuer_checks option is set.'),
                   30: ('X509_V_ERR_AKID_SKID_MISMATCH',
                        'authority and subject key identifier mismatch',
                        'the current candidate issuer certificate was rejected because its sub- ject key identifier was present and did not match the authority key identifier current certificate. Only displayed when the -issuer_checks option is set.'),
                   31: ('X509_V_ERR_AKID_ISSUER_SERIAL_MISMATCH',
                        'authority and issuer serial number mismatch',
                        'the current candidate issuer certificate was rejected because its issuer name and serial number was present and did not match the authority key identifier of the current certificate. Only displayed when the -issuer_checks option is set.'),
                   32: ('X509_V_ERR_KEYUSAGE_NO_CERTSIGN',
                        'key usage does not include certificate',
                        'signing the current candidate issuer certificate was rejected because its keyUsage extension does not permit certificate signing.'),
                   50: ('X509_V_ERR_APPLICATION_VERIFICATION',
                        'application verification failure',
                        'an application specific error. Unused.')}


    def __init__(self, cert, errno, depth):
        VerifyError.__init__(self, cert, errno, depth)
        self.cert = cert
        self.errno = errno
        self.depth = depth

    def __repr__(self):
        x = self._errorCodes.get(self.errno)
        if x is not None:
            name, short, long = x
            return 'Peer Certificate Verification Failed: %s (error code: %d)' % (
                long, self.errno
                )

    __str__ = __repr__

_x509namecrap = [
    ['CN', 'commonName'],
    ['O',  'organizationName'],
    ['OU', 'organizationalUnitName'],
    ['L',  'localityName'],
    ['ST', 'stateOrProvinceName'],
    ['C',  'countryName'],
    [      'emailAddress']]

_x509names = {}


for abbrevs in _x509namecrap:
    for abbrev in abbrevs:
        _x509names[abbrev] = abbrevs[0]

class DistinguishedName(dict):
    __slots__ = ()
    def __init__(self, **kw):
        for k, v in kw.iteritems():
            setattr(self, k, v)

    def _copyFrom(self, x509name):
        d = {}
        for name in _x509names:
            value = getattr(x509name, name, None)
            if value is not None:
                setattr(self, name, value)

    def _copyInto(self, x509name):
        for k, v in self.iteritems():
            setattr(x509name, k, v)

    def __repr__(self):
        return '<DN %s>' % (dict.__repr__(self)[1:-1])

    def __getattr__(self, attr):
        return self[_x509names[attr]]

    def __setattr__(self, attr, value):
        assert type(attr) is str
        if not attr in _x509names:
            raise AttributeError("%s is not a valid OpenSSL X509 name field" % (attr,))
        realAttr = _x509names[attr]
        value = value.encode('ascii')
        assert type(value) is str
        self[realAttr] = value

    def inspect(self):
        l = []
        from formless.annotate import nameToLabel
        lablen = 0
        for kp in _x509namecrap:
            k = kp[-1]
            label = nameToLabel(k)
            lablen = max(len(label), lablen)
            l.append((label, getattr(self, k)))
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
        return self._copyName('subject')



def problemsFromTransport(tpt):
    """Return a list of L{OpenSSLVerifyError}s given a Twisted transport object.
    """
    return tpt.getHandle().get_context().get_app_data().problems

class Certificate(CertBase):
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
        return Class(crypto.load_certificate(format, requestData), *args)
    load = classmethod(load)
    _load = load

    def dumpPEM(self):
        """Dump both public and private parts of a private certificate to PEM-format
        data
        """
        return self.dump(crypto.FILETYPE_PEM)

    def loadPEM(Class, data):
        """Load both private and public parts of a private certificate from a chunk of
        PEM-format data.
        """
        return Class.load(data, crypto.FILETYPE_PEM)
    loadPEM = classmethod(loadPEM)

    def peerFromTransport(Class, transport):
        return Class(transport.getHandle().get_peer_certificate())
    peerFromTransport = classmethod(peerFromTransport)

    def hostFromTransport(Class, transport):
        return Class(transport.getHandle().get_host_certificate())
    hostFromTransport = classmethod(hostFromTransport)

    def getPublicKey(self):
        return PublicKey(self.original.get_pubkey())

    def dump(self, format=crypto.FILETYPE_ASN1):
        return crypto.dump_certificate(format, self.original)

    def serialNumber(self):
        return self.original.get_serial_number()

    def digest(self, method='md5'):
        return self.original.digest(method)

    def _inspect(self):
        return '\n'.join(['Certificate For Subject:',
                          self.getSubject().inspect(),
                          '\nIssuer:',
                          self.getIssuer().inspect(),
                          '\nSerial Number: %d' % self.serialNumber(),
                          'Digest: %s' % self.digest()])

    def inspect(self):
        return '\n'.join(self._inspect(), self.getPublicKey().inspect())

    def getIssuer(self):
        return self._copyName('issuer')

    def options(self, *authorities):
        raise NotImplementedError('Possible, but doubtful we need this yet')

class CertificateRequest(CertBase):
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
    def __repr__(self):
        return Certificate.__repr__(self) + ' with ' + repr(self.privateKey)

    def _setPrivateKey(self, privateKey):
        if not privateKey.matches(self.getPublicKey()):
            raise VerifyError(
                "Sanity check failed: Your certificate was not properly signed.")
        self.privateKey = privateKey
        return self

    def newCertificate(self, newCertData, format=crypto.FILETYPE_ASN1):
        return self.load(newCertData, self.privateKey, format)

    def load(Class, data, privateKey, format=crypto.FILETYPE_ASN1):
        return Class._load(data, format)._setPrivateKey(privateKey)
    load = classmethod(load)

    def inspect(self):
        return '\n'.join([Certificate._inspect(self),
                          self.privateKey.inspect()])

    def dumpPEM(self):
        """Dump both public and private parts of a private certificate to PEM-format
        data
        """
        return self.dump(crypto.FILETYPE_PEM) + self.privateKey.dump(crypto.FILETYPE_PEM)

    def loadPEM(Class, data):
        """Load both private and public parts of a private certificate from a chunk of
        PEM-format data.
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

# O OG OMG OMFG PYOPENSSL SUCKS SO BAD
#     def verifyCertificate(self, certificate):
#         """returns None, or raises a VerifyError exception if the certificate could not
#         be verified.
#         """
#         if not certificate.original.verify(self.original):
#             raise VerifyError("We didn't sign that certificate.")

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.keyHash())

    def keyHash(self):
        """MD5 hex digest of signature on an empty certificate request with this key.
        """
        return md5.md5(self._emptyReq).hexdigest()

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
        """Given a blob of certificate request data and a certificate authority's
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
        dn = requestObject.getSubject()
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
    """A factory for SSL context objects, for server SSL connections.
    """

    _context = None
    # Older versions of PyOpenSSL didn't provide OP_ALL.  Fudge it here, just in case.
    _OP_ALL = getattr(SSL, 'OP_ALL', 0x0000FFFF)

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
                 fixBrokenPeers=False):
        """
        Create an OpenSSL context SSL connection context factory.

        @param privateKey: A PKey object holding the private key.

        @param certificate: An X509 object holding the certificate.

        @param method: The SSL protocol to use, one of SSLv23_METHOD,
        SSLv2_METHOD, SSLv3_METHOD, TLSv1_METHOD.  Defaults to TLSv1_METHOD.

        @param verify: If True, verify certificates received from the peer and
        fail the handshake if verification fails.  Otherwise, allow anonymous
        sessions and sessions with certificates which fail validation.  By
        default this is False.

        @param caCerts: List of certificate authority certificates to
        send to the client when requesting a certificate.  Only used if verify
        is True, and if verify is True, either this must be specified or
        caCertsFile must be given.  Since verify is False by default,
        this is None by default.

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
        """

        assert (privateKey is None) == (certificate is None), "Specify neither or both of privateKey and certificate"
        self.privateKey = privateKey
        self.certificate = certificate
        if method is not None:
            self.method = method

        self.verify = verify
        assert ((verify and caCerts) or
                (not verify)), "Specify client CA certificate information if and only if enabling certificate verification"

        self.caCerts = caCerts
        self.verifyDepth = verifyDepth
        self.requireCertificate = requireCertificate
        self.verifyOnce = verifyOnce
        self.enableSingleUseKeys = enableSingleUseKeys
        self.enableSessions = enableSessions
        self.fixBrokenPeers = fixBrokenPeers

    def __getstate__(self):
        d = super(OpenSSLCertificateOptions, self).__getstate__()
        try:
            del d['context']
        except KeyError:
            pass
        return d

    def getContext(self):
        """Return a SSL.Context object.
        """
        if self._context is None:
            self._context = self._makeContext()
        return self._context

    def _makeContext(self):
        ctx = SSL.Context(self.method)
        ctx.set_app_data(_SSLApplicationData())

        if self.certificate is not None and self.privateKey is not None:
            ctx.use_certificate(self.certificate)
            ctx.use_privatekey(self.privateKey)
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

        def _trackVerificationProblems(conn,cert,errno,depth,preverify_ok):
            # retcode is the answer OpenSSL's default verifier would have
            # given, had we allowed it to run.
            if not preverify_ok:
                ctx.get_app_data().problems.append(OpenSSLVerifyError(cert, errno, depth))
            return preverify_ok
        ctx.set_verify(verifyFlags, _trackVerificationProblems)

        if self.verifyDepth is not None:
            ctx.set_verify_depth(self.verifyDepth)

        if self.enableSingleUseKeys:
            ctx.set_options(SSL.OP_SINGLE_DH_USE)

        if self.fixBrokenPeers:
            ctx.set_options(self._OP_ALL)

        if self.enableSessions:
            sessionName = md5.md5("%s-%d" % (reflect.qual(self.__class__), _sessionCounter())).hexdigest()
            ctx.set_session_id(sessionName)

        return ctx
