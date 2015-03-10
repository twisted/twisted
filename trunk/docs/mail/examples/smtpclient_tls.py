
"""
Demonstrate sending mail via SMTP while employing TLS and performing
authentication.
"""

import sys

from OpenSSL.SSL import SSLv3_METHOD

from twisted.mail.smtp import ESMTPSenderFactory
from twisted.python.usage import Options, UsageError
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.defer import Deferred
from twisted.internet import reactor

def sendmail(
    authenticationUsername, authenticationSecret,
    fromAddress, toAddress,
    messageFile,
    smtpHost, smtpPort=25
    ):
    """
    @param authenticationUsername: The username with which to authenticate.
    @param authenticationSecret: The password with which to authenticate.
    @param fromAddress: The SMTP reverse path (ie, MAIL FROM)
    @param toAddress: The SMTP forward path (ie, RCPT TO)
    @param messageFile: A file-like object containing the headers and body of
    the message to send.
    @param smtpHost: The MX host to which to connect.
    @param smtpPort: The port number to which to connect.

    @return: A Deferred which will be called back when the message has been
    sent or which will errback if it cannot be sent.
    """

    # Create a context factory which only allows SSLv3 and does not verify
    # the peer's certificate.
    contextFactory = ClientContextFactory()
    contextFactory.method = SSLv3_METHOD

    resultDeferred = Deferred()

    senderFactory = ESMTPSenderFactory(
        authenticationUsername,
        authenticationSecret,
        fromAddress,
        toAddress,
        messageFile,
        resultDeferred,
        contextFactory=contextFactory)

    reactor.connectTCP(smtpHost, smtpPort, senderFactory)

    return resultDeferred



class SendmailOptions(Options):
    synopsis = "smtpclient_tls.py [options]"

    optParameters = [
        ('username', 'u', None,
         'The username with which to authenticate to the SMTP server.'),
        ('password', 'p', None,
         'The password with which to authenticate to the SMTP server.'),
        ('from-address', 'f', None,
         'The address from which to send the message.'),
        ('to-address', 't', None,
         'The address to which to send the message.'),
        ('message', 'm', None,
         'The filename which contains the message to send.'),
        ('smtp-host', 'h', None,
         'The host through which to send the message.'),
        ('smtp-port', None, '25',
         'The port number on smtp-host to which to connect.')]


    def postOptions(self):
        """
        Parse integer parameters, open the message file, and make sure all
        required parameters have been specified.
        """
        try:
            self['smtp-port'] = int(self['smtp-port'])
        except ValueError:
            raise UsageError("--smtp-port argument must be an integer.")
        if self['username'] is None:
            raise UsageError(
                "Must specify authentication username with --username")
        if self['password'] is None:
            raise UsageError(
                "Must specify authentication password with --password")
        if self['from-address'] is None:
            raise UsageError("Must specify from address with --from-address")
        if self['to-address'] is None:
            raise UsageError("Must specify from address with --to-address")
        if self['smtp-host'] is None:
            raise UsageError("Must specify smtp host with --smtp-host")
        if self['message'] is None:
            raise UsageError(
                "Must specify a message file to send with --message")
        try:
            self['message'] = file(self['message'])
        except Exception, e:
            raise UsageError(e)



def cbSentMessage(result):
    """
    Called when the message has been sent.

    Report success to the user and then stop the reactor.
    """
    print "Message sent"
    reactor.stop()



def ebSentMessage(err):
    """
    Called if the message cannot be sent.

    Report the failure to the user and then stop the reactor.
    """
    err.printTraceback()
    reactor.stop()



def main(args=None):
    """
    Parse arguments and send an email based on them.
    """
    o = SendmailOptions()
    try:
        o.parseOptions(args)
    except UsageError, e:
        raise SystemExit(e)
    else:
        from twisted.python import log
        log.startLogging(sys.stdout)
        result = sendmail(
            o['username'],
            o['password'],
            o['from-address'],
            o['to-address'],
            o['message'],
            o['smtp-host'],
            o['smtp-port'])
        result.addCallbacks(cbSentMessage, ebSentMessage)
        reactor.run()


if __name__ == '__main__':
    main(sys.argv[1:])
