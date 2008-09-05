from twisted.python import util

util.moduleMovedForSplit('twisted.protocols.pop3', 'twisted.mail.pop3',
                         'POP3 protocol support', 'Mail',
                         'http://twistedmatrix.com/trac/wiki/TwistedMail',
                         globals())
