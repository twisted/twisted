# -*- test-case-name: twisted.mail.test.test_options -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am the support module for creating mail servers with twistd
"""

import os
import sys

from twisted.mail import mail
from twisted.mail import maildir
from twisted.mail import relay
from twisted.mail import relaymanager
from twisted.mail import alias

from twisted.python import usage

from twisted.cred import checkers
from twisted.application import internet


class Options(usage.Options):
    synopsis = "[options]"

    optParameters = [
        ["pop3", "p", 8110, "Port to start the POP3 server on (0 to disable).", usage.portCoerce],
        ["pop3s", "S", 0, "Port to start the POP3-over-SSL server on (0 to disable).", usage.portCoerce],
        ["smtp", "s", 8025, "Port to start the SMTP server on (0 to disable).", usage.portCoerce],
        ["certificate", "c", None, "Certificate file to use for SSL connections"],
        ["relay", "R", None,
            "Relay messages according to their envelope 'To', using the given"
            "path as a queue directory."],
        ["hostname", "H", None, "The hostname by which to identify this server."],
    ]

    optFlags = [
        ["esmtp", "E", "Use RFC 1425/1869 SMTP extensions"],
        ["disable-anonymous", None, "Disallow non-authenticated SMTP connections"],
    ]
    zsh_actions = {"hostname" : "_hosts"}

    longdesc = "This creates a mail.tap file that can be used by twistd."

    def __init__(self):
        usage.Options.__init__(self)
        self.service = mail.MailService()
        self.last_domain = None

    def opt_passwordfile(self, filename):
        """Specify a file containing username:password login info for authenticated ESMTP connections."""
        ch = checkers.OnDiskUsernamePasswordDatabase(filename)
        self.service.smtpPortal.registerChecker(ch)
    opt_P = opt_passwordfile

    def opt_default(self):
        """Make the most recently specified domain the default domain."""
        if self.last_domain:
            self.service.addDomain('', self.last_domain)
        else:
            raise usage.UsageError("Specify a domain before specifying using --default")
    opt_D = opt_default

    def opt_maildirdbmdomain(self, domain):
        """generate an SMTP/POP3 virtual domain which saves to \"path\"
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

    def postOptions(self):
        if self['pop3s']:
            if not self['certificate']:
                raise usage.UsageError("Cannot specify --pop3s without "
                                       "--certificate")
            elif not os.path.exists(self['certificate']):
                raise usage.UsageError("Certificate file %r does not exist."
                                       % self['certificate'])

        if not self['disable-anonymous']:
            self.service.smtpPortal.registerChecker(checkers.AllowAnonymousAccess())

        if not (self['pop3'] or self['smtp'] or self['pop3s']):
            raise usage.UsageError("You cannot disable all protocols")

class AliasUpdater:
    def __init__(self, domains, domain):
        self.domains = domains
        self.domain = domain
    def __call__(self, new):
        self.domain.setAliasGroup(alias.loadAliasFile(self.domains, new))

def makeService(config):
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

    ctx = None
    if config['certificate']:
        from twisted.mail.protocols import SSLContextFactory
        ctx = SSLContextFactory(config['certificate'])

    if config['pop3']:
        s = internet.TCPServer(config['pop3'], config.service.getPOP3Factory())
        s.setServiceParent(config.service)
    if config['pop3s']:
        s = internet.SSLServer(config['pop3s'],
                               config.service.getPOP3Factory(), ctx)
        s.setServiceParent(config.service)
    if config['smtp']:
        f = smtpFactory()
        f.context = ctx
        if config['hostname']:
            f.domain = config['hostname']
            f.fArgs = (f.domain,)
        if config['esmtp']:
            f.fArgs = (None, None) + f.fArgs
        s = internet.TCPServer(config['smtp'], f)
        s.setServiceParent(config.service)
    return config.service
