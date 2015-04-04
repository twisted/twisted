from __future__ import print_function

from twisted.mail.smtp import sendmail
from twisted.internet import reactor

from email.mime.text import MIMEText

me = "alice@gmail.com"
to = ["bob@gmail.com", "charlie@gmail.com"]

message = MIMEText("This is my super awesome email, sent with Twisted!")
message["Subject"] = "Twisted is great!"
message["From"] = me
message["To"] = ", ".join(to)

d = sendmail("smtp.gmail.com", me, to, message,
             port=587, username=me, password="*********",
             requireAuthentication=True,
             requireTransportSecurity=True)

d.addBoth(print)
d.addCallback(lambda _: reactor.stop())

reactor.run()
