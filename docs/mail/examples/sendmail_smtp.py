from __future__ import print_function

from twisted.mail.smtp import sendmail
from twisted.internet import reactor

d = sendmail("myinsecuremailserver.example.com",
             "alice@example.com",
             ["bob@gmail.com", "charlie@gmail.com"],
             "This is my super awesome email, sent with Twisted!")

d.addBoth(print)
d.addCallback(lambda _: reactor.stop())

reactor.run()
