
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Examples
========

SMTP servers
------------

- :download:`emailserver.tac` - a toy email server.


SMTP clients
------------

- :download:`sendmail_smtp.py` - sending email over plain SMTP with the high-level :api:`twisted.mail.smtp.sendmail <sendmail>` client.
- :download:`sendmail_gmail.py` - sending email encrypted ESMTP to GMail with the high-level :api:`twisted.mail.smtp.sendmail <sendmail>` client.
- :download:`sendmail_message.py` - sending a complex message with the high-level :api:`twisted.mail.smtp.sendmail <sendmail>` client.
- :download:`smtpclient_simple.py` - sending email using SMTP.
- :download:`smtpclient_tls.py` - send email using authentication and transport layer security.


IMAP clients
------------

- :download:`imap4client.py` - Simple IMAP4 client which displays the subjects of all messages in a particular mailbox.
