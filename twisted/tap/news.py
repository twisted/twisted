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
from twisted.python import usage

import sys, getpass

class Options(usage.Options):
    synopsis = "Usage: mktap news [options]"

    optParameters = [
        ["port",       "p", "119",           "Listen port"],
        ["interface",  "i", "",              "Interface to which to bind"],
        
        ["groups",     "g", "groups.list",   "File containing group list"],
        ["servers",    "s", "servers.list",  "File containing server list"],
        
        ["backend",    "b", "sql",           "Backend type"]
    ]
    
    def postOptions(self):
        self['groups'] = [g.strip() for g in open(self['groups']).readlines() if not g.startswith('#')]
        self['servers'] = [s.strip() for s in open(self['servers']).readlines() if not s.startswith('#')]


def updateApplication(app, config):
    if config['backend'].lower() == 'sql':
        info = {
            'dbapiName': 'pyPgSQL.PgSQL', 'host': 'localhost',
            'user': 'news', 'database': 'news'
        }
        while 1:
            info['dbapiName'] = raw_input('DB-API 2.0 module [%s]: ' % (info['dbapiName'],)) or info['dbapiName']
            try:
                __import__(info['dbapiName'])
            except ImportError:
                print 'No such module'
            else:
                break

        info['host'] = raw_input('Database host [%s]: ' % (info['host'],)) or info['host']
        info['user'] = raw_input('Database username [%s]: ' % (info['user'],)) or info['user']
        info['database'] = raw_input('Database name [%s]: ' % (info['database'],)) or info['database']
        schema = raw_input('File to output SQL initialisation to [schema.sql]: ') or 'schema.sql'

        open(schema, 'w').write(
            database.NewsStorageAugmentation.schema + '\n' +
            database.makeGroupSQL(config['groups']) + '\n' +
            database.makeOverviewSQL()
        )
        db = database.NewsStorageAugmentation(info)
    elif config['backend'].lower() == 'pickle':
        filename = raw_input('Pickle file: ')
        db = database.PickleStorage(filename, config['groups'])
    else:
        raise usage.UsageError('Valid arguments to --backend are: sql pickle')

    app.listenTCP(
        int(config['port']),
        news.UsenetServerFactory(db, config['servers']),
        interface = config['interface']
    )
