from twisted.python import util

util.moduleMovedForSplit('twisted.protocols.imap4', 'twisted.mail.imap4',
                         'IMAP4 protocol support', 'Mail',
                         'http://twistedmatrix.com/trac/wiki/TwistedMail',
                         globals())

