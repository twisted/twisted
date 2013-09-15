#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example demonstrating how to generate a self-signed SSL
certificate using PyOpenSSl and twisted.internet.ssl. eg

 python make_certificate.py
"""

if __name__ == '__main__':
    import make_certificate
    raise SystemExit(make_certificate.main())



from datetime import datetime, timedelta
import sys

from OpenSSL import crypto

from twisted.internet import ssl
from twisted.python import usage


TIME_FORMAT = '%Y-%m-%d'


class Options(usage.Options):
    synopsis = 'Usage: make_certificate.py'

    optParameters = [
        ["key-type", "", "RSA", ""],
        ["key-length", "", "512", ""],
        ["valid-from", "", datetime.utcnow().strftime(TIME_FORMAT), ""],
        ["valid-to", "", (datetime.utcnow()
                          + timedelta(days=365)).strftime(TIME_FORMAT), ""],
        ["serial-number", "", "1", ""],
        ["digest-type", "", "md5", ""],
        ["subject", "", "Example Certificate", ""],
        ["common-name", "", "example.com", ""],
    ]



def makeCertificate(keyType, keyLength, serialNumber, digestType,
                    validFrom, validTo, **kw):
    """
    Generate OpenSSL keypair and certificate.
    """
    keypair = crypto.PKey()
    keypair.generate_key(keyType, keyLength)

    certificate = crypto.X509()
    certificate.gmtime_adj_notBefore(
        int((validFrom - datetime.utcnow()).total_seconds()))
    certificate.gmtime_adj_notAfter(
        int((validTo - datetime.utcnow()).total_seconds()))

    for xname in certificate.get_issuer(), certificate.get_subject():
        for (k, v) in kw.items():
            setattr(xname, k, v)

    certificate.set_serial_number(serialNumber)
    certificate.set_pubkey(keypair)
    certificate.sign(keypair, digestType)

    return keypair, certificate



def main(argv=sys.argv[1:]):
    options = Options()
    try:
        options.parseOptions(argv)
    except usage.UsageError as errortext:
        sys.stderr.write(str(options) + '\n')
        sys.stderr.write('ERROR: %s\n' % (errortext,))
        raise SystemExit(1)

    keyPair, certificate = makeCertificate(
        keyType=getattr(crypto, 'TYPE_' + options['key-type'].upper()),
        keyLength=int(options['key-length']),
        validFrom=datetime.strptime(options['valid-from'], TIME_FORMAT),
        validTo=datetime.strptime(options['valid-to'], TIME_FORMAT),
        serialNumber=int(options['serial-number']),
        digestType=options['digest-type'],
        O=options['subject'],
        CN=options['common-name'])

    keyPair = ssl.KeyPair(keyPair)
    keyFile = sys.stdout
    keyFile.write(keyPair.dump(format=crypto.FILETYPE_PEM))

    certificate = ssl.Certificate(certificate)
    certFile = sys.stdout
    certFile.write(certificate.dump(format=crypto.FILETYPE_PEM))
