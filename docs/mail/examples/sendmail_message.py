from email.mime.text import MIMEText

from twisted.internet.task import react
from twisted.mail.smtp import sendmail


def main(reactor):
    me = "alice@gmail.com"
    to = ["bob@gmail.com", "charlie@gmail.com"]

    message = MIMEText("This is my super awesome email, sent with Twisted!")
    message["Subject"] = "Twisted is great!"
    message["From"] = me
    message["To"] = ", ".join(to)

    d = sendmail(
        "smtp.gmail.com",
        me,
        to,
        message,
        port=587,
        username=me,
        password="*********",
        requireAuthentication=True,
        requireTransportSecurity=True,
    )

    d.addBoth(print)
    return d


react(main)
