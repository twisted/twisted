Sending Mail
============

Twisted contains many ways of sending email, but the simplest is :api:`twisted.mail.smtp.sendmail <sendmail>`.
Intended as a near drop-in replacement of :py:class:`smtplib.SMTP`\'s ``sendmail`` method, it provides the ability to send email over SMTP/ESMTP with minimal fuss or configuration.

Knowledge of Twisted's Deferreds is required for making full use of this document.


Sending an Email over SMTP
--------------------------

Although insecure, some email systems still use plain SMTP for sending email.
Plain SMTP has no authentication, no transport security (emails are transmitted in plain text), and should not be done over untrusted networks.

``sendmail``\'s positional arguments are, in order:

- The SMTP/ESMTP server you are sending the message to
- The email address you are sending from
- A ``list`` of email addresses you are sending to
- The message.

The following example shows these in action.

:download:`sendmail_smtp.py <../examples/sendmail_smtp.py>`

.. literalinclude:: ../examples/sendmail_smtp.py

Assuming that the values in it were replaced with real emails and a real SMTP server, it would send an email to the two addresses specified and print the return status.


Sending an Email over ESMTP
---------------------------

Extended SMTP (ESMTP) is an improved version of SMTP, and is used by most modern mail servers.
Unlike SMTP, ESMTP supports authentication and transport security (emails are encrypted in transit).
If you wish to send mail through services like GMail/Google Apps or Outlook.com/Office 365, you will have to use ESMTP.

Using ESMTP requires more options -- usually the default port of 25 is not open, so you must find out your email provider's TLS-enabled ESMTP port.
It also allows the use of authentication via a username and password.

The following example shows part of the ESMTP functionality of ``sendmail``.

:download:`sendmail_gmail.py <../examples/sendmail_gmail.py>`

.. literalinclude:: ../examples/sendmail_gmail.py

Assuming you own the account ``alice@gmail.com``, this would send an email to both ``bob@gmail.com`` and ``charlie@gmail.com``, and print out something like the following (formatted for clarity)::

  (2, [('bob@gmail.com', 250, '2.1.5 OK hz13sm11691456pac.6 - gsmtp'),
       ('charlie@gmail.com', 250, '2.1.5 OK hz13sm11691456pac.6 - gsmtp')])

``sendmail`` returns a 2-tuple, containing the number of emails sent successfully (note that this is from you to the server you specified, not to the recepient -- emails may still be lost between that server and the recepient) and a list of statuses of the sent mail.
Each status is a 3-tuple containing the address it was sent to, the SMTP status code, and the server response.


Sending Complex Emails
----------------------

Sometimes you want to send more complicated emails -- ones with headers, or with attachments.
``sendmail`` supports using Python's :py:class:`email.Message`, which lets you make complex emails:

:download:`sendmail_message.py <../examples/sendmail_message.py>`

.. literalinclude:: ../examples/sendmail_message.py

For more information on how to use ``Message``, please see :ref:`the module's Python docs <py2:email-examples>`.


Enforcing Transport Security
----------------------------

To prevent downgrade attacks, you can pass ``requireTransportSecurity=True`` to ``sendmail``.
This means that your emails will not be transmitted in plain text.

For example::

  sendmail("smtp.gmail.com", me, to, message,
           port=587, username=me, password="*********",
           requireTransportSecurity=True)


Conclusion
----------

In this document, you have seen how to:

#. Send an email over SMTP using :api:`twisted.mail.smtp.sendmail <sendmail>`.
#. Send an email over encrypted & authenticated ESMTP with :api:`twisted.mail.smtp.sendmail <sendmail>`.
#. Send a "complex" email containing a subject line using the stdlib's ``email.Message`` functionality.
#. Enforce transport security for emails sent using :api:`twisted.mail.smtp.sendmail <sendmail>`.
