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

from twisted.enterprise import adbapi
from twisted.news import news, database
from twisted.python import usage, log

import sys, getpass

class DBOptions(usage.Options):
    optParameters = [
        ['module',   None, 'pyPgSQL.PgSQL', "DB-API 2.0 module to use"],
        ['dbhost',   None, 'localhost',     "Host where database manager is listening"],
        ['dbuser',   None, 'news',          "Username with which to connect to database"],
        ['database', None, 'news',          "Database name to use"],
        ['schema',   None, 'schema.sql',    "File to which to write SQL schema initialisation"],

        # XXX - Hrm.
        ["groups",     "g", "groups.list",   "File containing group list"],
        ["servers",    "s", "servers.list",  "File containing server list"]
    ]
    
    def postOptions(self):
        # XXX - Hmmm.
        self['groups'] = [g.strip() for g in open(self['groups']).readlines() if not g.startswith('#')]
        self['servers'] = [s.strip() for s in open(self['servers']).readlines() if not s.startswith('#')]

        try:
            __import__(self['module'])
        except ImportError:
            log.msg("Warning: Cannot import %s" % (self['module'],))
        
        open(self['schema'], 'w').write(
            database.NewsStorageAugmentation.schema + '\n' +
            database.makeGroupSQL(self['groups']) + '\n' +
            database.makeOverviewSQL()
        )
        
        info = {
            'host': self['dbhost'], 'user': self['dbuser'],
            'database': self['database'], 'dbapiName': self['module']
        }
        self.db = database.NewsStorageAugmentation(info)


class PickleOptions(usage.Options):
    optParameters = [
        ['file', None, 'news.pickle', "File to which to save pickle"],

        # XXX - Hrm.
        ["groups",     "g", "groups.list",   "File containing group list"],
        ["servers",    "s", "servers.list",  "File containing server list"],
        ["moderators", "m", "moderators.list",
         "File containing moderators list"],
    ]
    
    subCommands = None

    def postOptions(self):
        # XXX - Hmmm.
        filename = self['file']
        self['groups'] = [g.strip() for g in open(self['groups']).readlines()
                          if not g.startswith('#')]
        self['servers'] = [s.strip() for s in open(self['servers']).readlines()
                           if not s.startswith('#')]
        self['moderators'] = [s.split()
                              for s in open(self['moderators']).readlines()
                              if not s.startswith('#')]
        self.db = database.PickleStorage(filename, self['groups'],
                                         self['moderators'])


class Options(usage.Options):
    synopsis = "Usage: mktap news [options]"
    
    groups = None
    servers = None
    subscriptions = None

    optParameters = [
        ["port",       "p", "119",           "Listen port"],
        ["interface",  "i", "",              "Interface to which to bind"],
        ["datadir",    "d", "news.db",       "Root data storage path"],
        ["mailhost",   "m", "localhost",     "Host of SMTP server to use"]
    ]

    def __init__(self):
        usage.Options.__init__(self)
        self.groups = []
        self.servers = []
        self.subscriptions = []


    def opt_group(self, group):
        """The name of a newsgroup to carry."""
        self.groups.append([group, None])


    def opt_moderator(self, moderator):
        """The email of the moderator for the most recently passed group."""
        self.groups[-1][1] = moderator


    def opt_subscription(self, group):
        """A newsgroup to list as a recommended subscription."""
        self.subscriptions.append(group)


    def opt_server(self, server):
        """The address of a Usenet server to pass messages to and receive messages from."""
        self.servers.append(server)


def updateApplication(app, config):
    if not len(config.groups):
        raise usage.UsageError("No newsgroups specified")
    
    db = database.NewsShelf(config['mailhost'], config['datadir'])
    for (g, m) in config.groups:
        if m:
            db.addGroup(g, 'm')
            db.addModerator(g, m)
        else:
            db.addGroup(g, 'y')
    for s in config.subscriptions:
        print s
        db.addSubscription(s)

    app.listenTCP(
        int(config['port']),
        news.UsenetServerFactory(db, config.servers),
        interface = config['interface']
    )
