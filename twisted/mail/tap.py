# -*- test-case-name: twisted.mail.test.test_options -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I am the support module for creating mail servers with twistd
"""

import os
import warnings

from twisted.mail import mail
from twisted.mail import maildir
from twisted.mail import relay
from twisted.mail import relaymanager
from twisted.mail import alias

from twisted.internet import endpoints

from twisted.python import usage

from twisted.cred import checkers
from twisted.cred import strcred

from twisted.application import internet


class Options(usage.Options, strcred.AuthOptionMixin):
    synopsis = "[options]"

    optParameters = [
        ["pop3s", "S", 0,
         "Port to start the POP3-over-SSL server on (0 to disable). "
         "DEPRECATED: use "
         "'--pop3 ssl:port:privateKey=pkey.pem:certKey=cert.pem'"],

        ["certificate", "c", None,
         "Certificate file to use for SSL connections. "
         "DEPRECATED: use "
         "'--pop3 ssl:port:privateKey=pkey.pem:certKey=cert.pem'"],

        ["relay", "R", None,
         "Relay messages according to their envelope 'To', using "
         "the given path as a queue directory."],

        ["hostname", "H", None,
         "The hostname by which to identify this server."],
    ]

    optFlags = [
        ["esmtp", "E", "Use RFC 1425/1869 SMTP extensions"],
        ["disable-anonymous", None,
         "Disallow non-authenticated SMTP connections"],
        ["no-pop3", None, "Disable the default POP3 server."],
        ["no-smtp", None, "Disable the default SMTP server."],
    ]

    _protoDefaults = {
        "pop3": 8110,
        "smtp": 8025,
    }

    compData = usage.Completions(
                   optActions={"hostname" : usage.CompleteHostnames(),
                               "certificate" : usage.CompleteFiles("*.pem")}
                   )

    longdesc = """
    An SMTP / POP3 email server plugin for twistd.

    Examples:

    1. SMTP and POP server

    twistd mail --maildirdbmdomain=example.com=/tmp/example.com
    --user=joe=password

    Starts an SMTP server that only accepts emails to joe@example.com and saves
    them to /tmp/example.com.

    Also starts a POP mail server which will allow a client to log in using
    username: joe@example.com and password: password and collect any email that
    has been saved in /tmp/example.com.  

    2. SMTP relay

    twistd mail --relay=/tmp/mail_queue

    Starts an SMTP server that accepts emails to any email address and relays
    them to an appropriate remote SMTP server. Queued emails will be
    temporarily stored in /tmp/mail_queue.
    """

    def __init__(self):
        usage.Options.__init__(self)
        self.service = mail.MailService()
        self.last_domain = None
        for service in self._protoDefaults:
            self[service] = []


    def addEndpoint(self, service, description, certificate=None):
        """
        Given a 'service' (pop3 or smtp), add an endpoint.
        """
        self[service].append(
            _toEndpoint(description, certificate=certificate))


    def opt_pop3(self, description):
        """
        Add a pop3 port listener on the specified endpoint.  You can listen on
        multiple ports by specifying multiple --pop3 options.  For backwards
        compatibility, a bare TCP port number can be specified, but this is
        deprecated. [SSL Example: ssl:8995:privateKey=mycert.pem] [default:
        tcp:8110]
        """
        self.addEndpoint('pop3', description)
    opt_p = opt_pop3


    def opt_smtp(self, description):
        """
        Add an smtp port listener on the specified endpoint.  You can listen on
        multiple ports by specifying multiple --smtp options For backwards
        compatibility, a bare TCP port number can be specified, but this is
        deprecated.  [SSL Example: ssl:8465:privateKey=mycert.pem] [default:
        tcp:8025]
        """
        self.addEndpoint('smtp', description)
    opt_s = opt_smtp


    def opt_default(self):
        """Make the most recently specified domain the default domain."""
        if self.last_domain:
            self.service.addDomain('', self.last_domain)
        else:
            raise usage.UsageError("Specify a domain before specifying using --default")
    opt_D = opt_default


    def opt_maildirdbmdomain(self, domain):
        """Generate an SMTP/POP3 virtual domain. This option requires
        an argument of the form 'NAME=PATH' where NAME is the DNS
        Domain Name for which email will be accepted and where PATH is
        a the filesystem path to a Maildir folder. [Example:
        'example.com=/tmp/example.com']
        """
        try:
            name, path = domain.split('=')
        except ValueError:
            raise usage.UsageError("Argument to --maildirdbmdomain must be of the form 'name=path'")

        self.last_domain = maildir.MaildirDirdbmDomain(self.service, os.path.abspath(path))
        self.service.addDomain(name, self.last_domain)
    opt_d = opt_maildirdbmdomain

    def opt_user(self, user_pass):
        """add a user/password to the last specified domains
        """
        try:
            user, password = user_pass.split('=', 1)
        except ValueError:
            raise usage.UsageError("Argument to --user must be of the form 'user=password'")
        if self.last_domain:
            self.last_domain.addUser(user, password)
        else:
            raise usage.UsageError("Specify a domain before specifying users")
    opt_u = opt_user

    def opt_bounce_to_postmaster(self):
        """undelivered mails are sent to the postmaster
        """
        self.last_domain.postmaster = 1
    opt_b = opt_bounce_to_postmaster

    def opt_aliases(self, filename):
        """Specify an aliases(5) file to use for this domain"""
        if self.last_domain is not None:
            if mail.IAliasableDomain.providedBy(self.last_domain):
                aliases = alias.loadAliasFile(self.service.domains, filename)
                self.last_domain.setAliasGroup(aliases)
                self.service.monitor.monitorFile(
                    filename,
                    AliasUpdater(self.service.domains, self.last_domain)
                )
            else:
                raise usage.UsageError(
                    "%s does not support alias files" % (
                        self.last_domain.__class__.__name__,
                    )
                )
        else:
            raise usage.UsageError("Specify a domain before specifying aliases")
    opt_A = opt_aliases

    def _getEndpoints(self, reactor, service):
        """
        Return a list of endpoints for the specified service, constructing
        defaults if necessary.

        @param reactor: If any endpoints are created, this is the reactor with
            which they are created.

        @param service: A key into self indicating the type of service to
            retrieve endpoints for.  This is either C{"pop3"} or C{"smtp"}.

        @return: A C{list} of C{IServerStreamEndpoint} providers corresponding
            to the command line parameters that were specified for C{service}.
            If none were and the protocol was not explicitly disabled with a
            I{--no-*} option, a default endpoint for the service is created
            using C{self._protoDefaults}.
        """
        if service == 'pop3' and self['pop3s'] and len(self[service]) == 1:
            # The single endpoint here is the POP3S service we added in
            # postOptions.  Include the default endpoint alongside it.
            return self[service] + [
                endpoints.TCP4ServerEndpoint(
                    reactor, self._protoDefaults[service])]
        elif self[service]:
            # For any non-POP3S case, if there are any services set up, just
            # return those.
            return self[service]
        elif self['no-' + service]:
            # If there are no services, but the service was explicitly disabled,
            # return nothing.
            return []
        else:
            # Otherwise, return the old default service.
            return [
                endpoints.TCP4ServerEndpoint(
                    reactor, self._protoDefaults[service])]


    def postOptions(self):
        from twisted.internet import reactor

        if self['pop3s']:
            if not self['certificate']:
                raise usage.UsageError("Cannot specify --pop3s without "
                                       "--certificate")
            elif not os.path.exists(self['certificate']):
                raise usage.UsageError("Certificate file %r does not exist."
                                       % self['certificate'])
            else:
                self.addEndpoint(
                    'pop3', self['pop3s'], certificate=self['certificate'])

        if self['esmtp'] and self['hostname'] is None:
            raise usage.UsageError("--esmtp requires --hostname")

        # If the --auth option was passed, this will be present -- otherwise,
        # it won't be, which is also a perfectly valid state.
        if 'credCheckers' in self:
            for ch in self['credCheckers']:
                self.service.smtpPortal.registerChecker(ch)

        if not self['disable-anonymous']:
            self.service.smtpPortal.registerChecker(checkers.AllowAnonymousAccess())

        anything = False
        for service in self._protoDefaults:
            self[service] = self._getEndpoints(reactor, service)
            if self[service]:
                anything = True

        if not anything:
            raise usage.UsageError("You cannot disable all protocols")



class AliasUpdater:
    def __init__(self, domains, domain):
        self.domains = domains
        self.domain = domain
    def __call__(self, new):
        self.domain.setAliasGroup(alias.loadAliasFile(self.domains, new))


def _toEndpoint(description, certificate=None):
    """
    Tries to guess whether a description is a bare TCP port or a endpoint.  If a
    bare port is specified and a certificate file is present, returns an
    SSL4ServerEndpoint and otherwise returns a TCP4ServerEndpoint.
    """
    from twisted.internet import reactor
    try:
        port = int(description)
    except ValueError:
        return endpoints.serverFromString(reactor, description)

    warnings.warn(
        "Specifying plain ports and/or a certificate is deprecated since "
        "Twisted 11.0; use endpoint descriptions instead.",
        category=DeprecationWarning, stacklevel=3)

    if certificate:
        from twisted.internet.ssl import DefaultOpenSSLContextFactory
        ctx = DefaultOpenSSLContextFactory(certificate, certificate)
        return endpoints.SSL4ServerEndpoint(reactor, port, ctx)
    return endpoints.TCP4ServerEndpoint(reactor, port)


def makeService(config):
    """
    Construct a service for operating a mail server.

    The returned service may include POP3 servers or SMTP servers (or both),
    depending on the configuration passed in.  If there are multiple servers,
    they will share all of their non-network state (eg, the same user accounts
    are available on all of them).

    @param config: An L{Options} instance specifying what servers to include in
        the returned service and where they should keep mail data.

    @return: An L{IService} provider which contains the requested mail servers.
    """
    if config['esmtp']:
        rmType = relaymanager.SmartHostESMTPRelayingManager
        smtpFactory = config.service.getESMTPFactory
    else:
        rmType = relaymanager.SmartHostSMTPRelayingManager
        smtpFactory = config.service.getSMTPFactory

    if config['relay']:
        dir = config['relay']
        if not os.path.isdir(dir):
            os.mkdir(dir)

        config.service.setQueue(relaymanager.Queue(dir))
        default = relay.DomainQueuer(config.service)

        manager = rmType(config.service.queue)
        if config['esmtp']:
            manager.fArgs += (None, None)
        manager.fArgs += (config['hostname'],)

        helper = relaymanager.RelayStateHelper(manager, 1)
        helper.setServiceParent(config.service)
        config.service.domains.setDefaultDomain(default)

    if config['pop3']:
        f = config.service.getPOP3Factory()
        for endpoint in config['pop3']:
            svc = internet.StreamServerEndpointService(endpoint, f)
            svc.setServiceParent(config.service)

    if config['smtp']:
        f = smtpFactory()
        if config['hostname']:
            f.domain = config['hostname']
            f.fArgs = (f.domain,)
        if config['esmtp']:
            f.fArgs = (None, None) + f.fArgs
        for endpoint in config['smtp']:
            svc = internet.StreamServerEndpointService(endpoint, f)
            svc.setServiceParent(config.service)

    return config.service
