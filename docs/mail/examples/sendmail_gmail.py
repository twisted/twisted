from __future__ import print_function

from twisted.mail.smtp import sendmail
from twisted.internet.task import react

def main(reactor):

    d = sendmail("smtp.gmail.com",
                 "alice@gmail.com",
                 ["bob@gmail.com", "charlie@gmail.com"],
                 "This is my super awesome email, sent with Twisted!",
                 port=587, username="alice@gmail.com", password="*********")

    d.addBoth(print)
    return d

react(main)
