from twisted.python import util

util.moduleMovedForSplit('twisted.protocols.smtp', 'twisted.mail.smtp',
                         'SMTP protocol support', 'Mail',
                         'http://twistedmatrix.com/projects/mail',
                         globals())
