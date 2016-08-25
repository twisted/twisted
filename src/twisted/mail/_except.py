# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Exceptions in L{twisted.mail}.
"""

from __future__ import absolute_import, division


class IMAP4Exception(Exception):
    pass


class IllegalClientResponse(IMAP4Exception):
    pass



class IllegalOperation(IMAP4Exception):
    pass



class IllegalMailboxEncoding(IMAP4Exception):
    pass



class SMTPError(Exception):
    pass


class SMTPClientError(SMTPError):
    """
    Base class for SMTP client errors.
    """
    def __init__(self, code, resp, log=None, addresses=None, isFatal=False,
                 retry=False):
        """
        @param code: The SMTP response code associated with this error.

        @param resp: The string response associated with this error.

        @param log: A string log of the exchange leading up to and including
            the error.
        @type log: L{str}

        @param isFatal: A boolean indicating whether this connection can
            proceed or not. If True, the connection will be dropped.

        @param retry: A boolean indicating whether the delivery should be
            retried. If True and the factory indicates further retries are
            desirable, they will be attempted, otherwise the delivery will be
            failed.
        """
        self.code = code
        self.resp = resp
        self.log = log
        self.addresses = addresses
        self.isFatal = isFatal
        self.retry = retry


    def __str__(self):
        if self.code > 0:
            res = ["%.3d %s" % (self.code, self.resp)]
        else:
            res = [self.resp]
        if self.log:
            res.append(self.log)
            res.append('')
        return '\n'.join(res)



class ESMTPClientError(SMTPClientError):
    """
    Base class for ESMTP client errors.
    """



class EHLORequiredError(ESMTPClientError):
    """
    The server does not support EHLO.

    This is considered a non-fatal error (the connection will not be dropped).
    """



class AUTHRequiredError(ESMTPClientError):
    """
    Authentication was required but the server does not support it.

    This is considered a non-fatal error (the connection will not be dropped).
    """



class TLSRequiredError(ESMTPClientError):
    """
    Transport security was required but the server does not support it.

    This is considered a non-fatal error (the connection will not be dropped).
    """



class AUTHDeclinedError(ESMTPClientError):
    """
    The server rejected our credentials.

    Either the username, password, or challenge response
    given to the server was rejected.

    This is considered a non-fatal error (the connection will not be
    dropped).
    """



class AuthenticationError(ESMTPClientError):
    """
    An error occurred while authenticating.

    Either the server rejected our request for authentication or the
    challenge received was malformed.

    This is considered a non-fatal error (the connection will not be
    dropped).
    """



class TLSError(ESMTPClientError):
    """
    An error occurred while negiotiating for transport security.

    This is considered a non-fatal error (the connection will not be dropped).
    """



class SMTPConnectError(SMTPClientError):
    """
    Failed to connect to the mail exchange host.

    This is considered a fatal error.  A retry will be made.
    """
    def __init__(self, code, resp, log=None, addresses=None, isFatal=True,
                 retry=True):
        SMTPClientError.__init__(self, code, resp, log, addresses, isFatal,
                                 retry)



class SMTPTimeoutError(SMTPClientError):
    """
    Failed to receive a response from the server in the expected time period.

    This is considered a fatal error.  A retry will be made.
    """
    def __init__(self, code, resp, log=None, addresses=None, isFatal=True,
                 retry=True):
        SMTPClientError.__init__(self, code, resp, log, addresses, isFatal,
                                 retry)



class SMTPProtocolError(SMTPClientError):
    """
    The server sent a mangled response.

    This is considered a fatal error.  A retry will not be made.
    """
    def __init__(self, code, resp, log=None, addresses=None, isFatal=True,
                 retry=False):
        SMTPClientError.__init__(self, code, resp, log, addresses, isFatal,
                                 retry)



class SMTPDeliveryError(SMTPClientError):
    """
    Indicates that a delivery attempt has had an error.
    """



class SMTPServerError(SMTPError):
    def __init__(self, code, resp):
        self.code = code
        self.resp = resp

    def __str__(self):
        return "%.3d %s" % (self.code, self.resp)



class SMTPAddressError(SMTPServerError):
    def __init__(self, addr, code, resp):
        from twisted.mail.smtp import Address

        SMTPServerError.__init__(self, code, resp)
        self.addr = Address(addr)

    def __str__(self):
        return "%.3d <%s>... %s" % (self.code, self.addr, self.resp)



class SMTPBadRcpt(SMTPAddressError):
    def __init__(self, addr, code=550,
                 resp='Cannot receive for specified address'):
        SMTPAddressError.__init__(self, addr, code, resp)



class SMTPBadSender(SMTPAddressError):
    def __init__(self, addr, code=550, resp='Sender not acceptable'):
        SMTPAddressError.__init__(self, addr, code, resp)



class AddressError(SMTPError):
    """
    Parse error in address
    """
