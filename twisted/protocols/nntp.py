from twisted.python import util

util.moduleMovedForSplit('twisted.protocols.nntp', 'twisted.news.nntp',
                         'NNTP protocol support', 'News',
                         'http://twistedmatrix.com/projects/news',
                         globals())

