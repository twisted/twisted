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

"""Coil plugin for the mail service."""

# Twisted Imports
from twisted.protocols import protocol, pop3, smtp
from twisted.coil import coil
from twisted.mail import mail, maildir
from twisted.python import components

# System Imports
import types
import os


class MailConfigurator(coil.Configurator, coil.ConfigCollection):
    
    __implements__ = [coil.IConfigurator, coil.IConfigCollection]
    
    configurableClass = mail.MailService
    
    entityType = mail.IDomain
    
    configTypes = {
        'serviceName': [types.StringType, "Service Name", ""],
        'storagePath': [types.StringType, "Storage Path", "Folder where messages will be stored."],
        }
    
    def __init__(self, instance):
        coil.Configurator.__init__(self, instance)
        coil.ConfigCollection.__init__(self, instance.domains.domains)
    
    def configDispensers(self):
        return [
            ['makePOP3Server', protocol.IFactory, "POP3 server for %s" % self.instance.serviceName],
            ['makeSMTPServer', protocol.IFactory, "SMTP server for %s" % self.instance.serviceName]
            ]

    def makePOP3Server(self):
        return mail.createDomainsFactory(pop3.VirtualPOP3, self.instance.domains)
    
    def makeSMTPServer(self):
        return mail.createDomainsFactory(smtp.DomainSMTP, self.instance.domains)
    
    configName = 'Twisted Mail Service'

    def config_name(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")

    def config_storagePath(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        self.instance.storagePath = path

def mailFactory(container, name):
    return mail.MailService(name, container.app)

coil.registerConfigurator(MailConfigurator, mailFactory)
components.registerAdapter(MailConfigurator, mail.MailService, coil.IConfigCollection)


class MaildirDBMConfigurator(coil.Configurator, coil.ConfigCollection):

    __implements__ = [coil.IConfigurator, coil.IConfigCollection]
    
    entityType = types.StringType
    
    configurableClass = maildir.MaildirDirdbmDomain
    
    configTypes = {
        "postmaster": ["boolean", "Postmaster", "Do bounces get send to postmaster?"],
    }

    configName = 'Maildir DBM Domain'

    def __init__(self, instance):
        coil.Configurator.__init__(self, instance)
        coil.ConfigCollection.__init__(self, instance.dbm)

    def getEntityType(self):
        return "Password"
    
    def reallyPutEntity(self, name, entity):
        self.instance.dbm[name] = entity
        self.instance.userDirectory(name) # make maildir

def maildirDbmFactory(container, name):
    if components.implements(container, coil.IConfigurator):
        container = container.getInstance()
    path = os.path.join(container.storagePath, name)
    if not os.path.exists(path):
        os.makedirs(path)
    return maildir.MaildirDirdbmDomain(path)

coil.registerConfigurator(MaildirDBMConfigurator, maildirDbmFactory)
components.registerAdapter(MaildirDBMConfigurator, maildir.MaildirDirdbmDomain, coil.IConfigCollection)
