
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
from twisted.mail import mail, maildir, relay, relaymanager
from twisted.protocols import pop3, smtp
from twisted.python import usage, delay

import sys

class Options(usage.Options):
    synopsis = "Usage: mktap mail [options]"

    optParameters = [["pop", "p", 8110, "Port to start the POP3 server on."],
                  ["smtp", "s", 8025,
                   "Port to start the SMTP server on."],
                  ["relay", "r", None,
                   "relay mail we do not know how to handle to this IP,"
                   " using the given path as a queue directory"]]

    longdesc = "This creates a mail.tap file that can be used by twistd."

    def __init__(self):
    	self.service = mail.MailService("twisted.mail")
        self.last_domain = None
        usage.Options.__init__(self)

    def opt_domain(self, domain):
        """generate an SMTP/POP3 virtual domain which saves to \"path\"
        """

        name, path = string.split(domain, '=')
        self.last_domain = maildir.MaildirDirdbmDomain(self.service, os.path.abspath(path))
        self.service.domains[name] = self.last_domain
    opt_d = opt_domain

    def opt_user(self, user_pass):
        """add a user/password to the last specified domains
        """
        user, password = string.split(user_pass, '=')
        self.last_domain.dbm[user] = password
    opt_u = opt_user

    def opt_bounce_to_postmaster(self):
        """undelivered mails are sent to the postmaster
        """
        self.last_domain.postmaster = 1
    opt_b = opt_bounce_to_postmaster


def updateApplication(app, config):
    if config.opts['relay']:
        addr, dir = string.split(config.opts['relay'], '=', 1)
        ip, port = string.split(addr, ',', 1)
        port = int(port)
        config.service.setQueue(relaymanager.Queue(dir))
        default = relay.DomainQueuer(config.service)
        delayed = delay.Delayed()
        manager = relaymanager.SmartHostSMTPRelayingManager(config.service.queue, (ip, port))
        relaymanager.attachManagerToDelayed(manager, delayed)
        config.service.domains.setDefaultDomain(default)
        app.addDelayed(delayed)
    app.listenTCP(int(config.opts['pop']), config.service.getPOP3Factory())
    app.listenTCP(int(config.opts['smtp']), config.service.getSMTPFactory())
