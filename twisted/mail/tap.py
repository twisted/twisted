
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""I am the support module for creating mail servers with 'mktap'
"""

import string, os

# Twisted Imports
import mail, maildir, relay, relaymanager
from twisted.protocols import pop3, smtp
from twisted.python import usage, delay

import sys

class Options(usage.Options):
    synopsis = "Usage: mktap mail [options]"

    optParameters = [
        ["pop3", "p", 8110, "Port to start the POP3 server on (0 to disable)."],
        ["pop3s", "S", 0, "Port to start the POP3-over-SSL server on (0 to disable)."],
        ["smtp", "s", 8025, "Port to start the SMTP server on (0 to disable)."],
        ["relay", "r", None, 
            "relay mail we do not know how to handle to this IP,"
            " using the given path as a queue directory"],
        ["certificate", "c", None, "Certificate file to use for SSL connections"]
    ]

    longdesc = "This creates a mail.tap file that can be used by twistd."

    def __init__(self):
    	self.service = mail.MailService("twisted.mail")
        self.last_domain = None
        usage.Options.__init__(self)

    def opt_domain(self, domain):
        """generate an SMTP/POP3 virtual domain which saves to \"path\"
        """
        try:
            name, path = string.split(domain, '=')
        except ValueError:
            raise usage.UsageError("Argument to --domain must be of the form 'name=path'")
        self.last_domain = maildir.MaildirDirdbmDomain(self.service, os.path.abspath(path))
        self.service.domains[name] = self.last_domain
    opt_d = opt_domain

    def opt_user(self, user_pass):
        """add a user/password to the last specified domains
        """
        try:
            user, password = string.split(user_pass, '=')
        except ValueError:
            raise usage.UsageError("Argument to --user must be of the form 'user=password'")
        self.last_domain.dbm[user] = password
    opt_u = opt_user

    def opt_bounce_to_postmaster(self):
        """undelivered mails are sent to the postmaster
        """
        self.last_domain.postmaster = 1
    opt_b = opt_bounce_to_postmaster
    
    
    def postOptions(self):
        try:
            self['pop3'] = int(self['pop3'])
            assert 0 <= self['pop3'] < 2 ** 16, ValueError
        except ValueError:
            raise usage.UsageError('Invalid port specified to --pop3: %s' %
                                   self['pop3'])
        try:
            self['smtp'] = int(self['smtp'])
            assert 0 <= self['smtp'] < 2 ** 16, ValueError
        except ValueError:
            raise usage.UsageError('Invalid port specified to --smtp: %s' %
                                   self['smtp'])
        try:
            self['pop3s'] = int(self['pop3s'])
            assert 0 <= self['pop3s'] < 2 ** 16, ValueError
        except ValueError:
            raise usage.UsageError('Invalid port specified to --pop3s: %s' %
                                   self['pop3s'])
        else:
            if self['pop3s']:
                if not self['certificate']:
                    raise usage.UsageError("Cannot specify --pop3s without "
                                           "--certificate")
                elif not os.path.exists(self['certificate']):
                    raise usage.UsageError("Certificate file %r does not exist."
                                           % self['certificate'])
        if not (self['pop3'] or self['smtp'] or self['pop3s']):
            raise usage.UsageError("You cannot disable all protocols")

def updateApplication(app, config):
    if config['relay']:
        addr, dir = string.split(config['relay'], '=', 1)
        ip, port = string.split(addr, ',', 1)
        port = int(port)
        config.service.setQueue(relaymanager.Queue(dir))
        default = relay.DomainQueuer(config.service)
        delayed = delay.Delayed()
        manager = relaymanager.SmartHostSMTPRelayingManager(config.service.queue, (ip, port))
        relaymanager.attachManagerToDelayed(manager, delayed)
        config.service.domains.setDefaultDomain(default)
        app.addDelayed(delayed)
    
    if config['pop3']:
        app.listenTCP(config['pop3'], config.service.getPOP3Factory())
    if config['pop3s']:
        from twisted.mail.protocols import SSLContextFactory
        app.listenSSL(
            config['pop3s'],
            config.service.getPOP3Factory(),
            SSLContextFactory(config['certificate'])
        )
    if config['smtp']:
        app.listenTCP(config['smtp'], config.service.getSMTPFactory())
