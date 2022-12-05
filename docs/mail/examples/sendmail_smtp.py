from twisted.internet.task import react
from twisted.mail.smtp import sendmail


def main(reactor):
    d = sendmail(
        "myinsecuremailserver.example.com",
        "alice@example.com",
        ["bob@gmail.com", "charlie@gmail.com"],
        "This is my super awesome email, sent with Twisted!",
    )

    d.addBoth(print)
    return d


react(main)
