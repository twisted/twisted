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

from twisted.news import news, database
from twisted.python import usage

class Options(usage.Options):
    synopsis = "Usage: mktap news [options]"
    
    optParameters = [
        ["port", "p", "119", "Listen port"],
        ["database", "d", "pickle", "Message storage backend"],
        ["filename", "f", None, "Pickle file name"],
        ["groups", "g", None, "News groups to run"]
    ]


def updateApplication(app, config):
    # key - storage name
    # value - 2-tuple of storage class and tuple of additional options to
    #         find and pass to the storage class constructor
    BACK = {'pickle': (database.PickleStorage, ('filename',))}

    if not BACK.has_key(config.opts['database']):
        raise usage.UsageError("backend must be one of: %s" % ' '.join(BACK.keys()))
    else:
        x = BACK[config.opts['database']]
        db = x[0]
        opts = {}
        for i in x[1]:
            if config.opts.has_key(i) and config.opts[i]:
                opts[i] = config.opts[i]
            else:
                raise usage.UsageError("Missing required option: %s" % i)

    opts['groups'] = config.opts['groups'] and config.opts['groups'].split() or []

    app.listenTCP(
        int(config.opts['port']),

        # XXX This isn't *very* bad, is it?
        news.NNTPFactory(apply(db, (), opts))
    )
