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
        ["servers",    "s", "servers.list",  "File containing server list"]
    ]

    def postOptions(self):
        # XXX - Hmmm.
        self['groups'] = [g.strip() for g in open(self['groups']).readlines() if not g.startswith('#')]
        self['servers'] = [s.strip() for s in open(self['servers']).readlines() if not s.startswith('#')]

        self.db = database.PickleStorage(filename, self['groups'])


class Options(usage.Options):
    synopsis = "Usage: mktap news [options]"

    optParameters = [
        ["port",       "p", "119",           "Listen port"],
        ["interface",  "i", "",              "Interface to which to bind"],
    ]
    
    subCommands = [
        ['sql',    None, DBOptions,     'Create an SQL RDBM backed news server'],
        ['pickle', None, PickleOptions, 'Create a Pickle backed news server']
    ]


def updateApplication(app, config):
    if not hasattr(config, 'subCommand'):
        raise usage.UsageError("Must specify a subcommand.")
    app.listenTCP(
        int(config['port']),
        news.UsenetServerFactory(config.subOptions.db, config.subOptions['servers']),
        interface = config['interface']
    )
