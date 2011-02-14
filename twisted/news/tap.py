# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.news import news, database
from twisted.application import strports
from twisted.python import usage, log

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
        
        f = open(self['schema'], 'w')
        f.write(
            database.NewsStorageAugmentation.schema + '\n' +
            database.makeGroupSQL(self['groups']) + '\n' +
            database.makeOverviewSQL()
        )
        f.close()
        
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
    synopsis = "[options]"
    
    groups = None
    servers = None
    subscriptions = None

    optParameters = [
        ["port",       "p", "119",           "Listen port"],
        ["interface",  "i", "",              "Interface to which to bind"],
        ["datadir",    "d", "news.db",       "Root data storage path"],
        ["mailhost",   "m", "localhost",     "Host of SMTP server to use"]
    ]
    zsh_actions = {"datadir" : "_dirs", "mailhost" : "_hosts"}

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


def makeService(config):
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
    s = config['port']
    if config['interface']:
        # Add a warning here
        s += ':interface='+config['interface']
    return strports.service(s, news.UsenetServerFactory(db, config.servers))
