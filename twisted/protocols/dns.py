from twisted.python import util

util.moduleMovedForSplit('twisted.protocols.dns', 'twisted.names.dns',
                         'DNS protocol support', 'Names',
                         'http://projects.twistedmatrix.com/names',
                         globals())
