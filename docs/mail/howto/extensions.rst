Implementing ESMTP Extensions
=============================

Twisted includes a minimal ESMTP server, :api:`twisted.mail.smtp.ESMTP`, which
by default offers only ``AUTH`` and ``STARTTLS`` extensions, dependent on
whether you have specified challengers and a TLS capable transport
respectively.

If you wish to implement you own extensions, the first thing you will need to
do is to subclass :api:`twisted.mail.smtp.ESMTP` and override the
``extensions`` method (note that Twisted uses old-style classes here, so you
cannot use ``super``).

.. code-block:: python

    from twisted.mail import smtp

    class ExtendedESMTP(smtp.ESMTP):

        def extensions(self):
            ext = smtp.ESMTP.extensions(self)
            ext['HELLO'] = None
            return ext

This will cause the server to announce your extension in response to the
``EHLO`` command.

To add a new command, implement a ``do_COMMAND`` message

.. code-block:: python

    class ExtendedESMTP(smtp.ESMTP):

        ...

        def do_SAYHELLO(self):
            self.sendCode(250, 'Hello World!')

If your extension specifies ESMTP options on the ``MAIL FROM:`` command, you
can find them in a dictionary member variable, ``options``.  Options
specified on ``MAIL FROM:`` are global and do not necessarily relate to the
sender.  For example, let’s add a ``NICKNAME`` option that we can use to
customize the reply from our ``SAYHELLO`` command.

.. code-block:: python

    class ExtendedESMTP(smtp.ESMTP):

        ...

        def do_SAYHELLO(self):
            name = self.options.get('NICKNAME', 'my anonymous friend')
            self.sendCode(250, 'Hello %s' % name)

ESMTP also allows for options on the ``RCPT TO:`` command.  Since there can be
multiple ``RCPT TO:`` commands in a given mailserver dialog, options specified
on ``RCPT TO:`` are associated with a :api:`twisted.mail.smtp.User` object,
and can be accessed using the `options` attribute of that object.  For
instance

.. code-block:: python

    class MyMessage:
        implements(smtp.IMessage)

        ...

    class MyMessageDelivery:
        implements(smtp.IMessageDelivery)

        def validateFrom(self, helo, origin):
            return origin

        def validateTo(self, user):
            if user.options.get('HAS-WILD-PARTIES', 'no') != 'no':
                raise SMTPBadRcpt('Cannot send to people who have wild parties')
            return lambda: MyMessage()

It is also permissible for an ``ESMTP`` subclass to switch to raw mode; you
might do this if you were trying to implement the ``CHUNKING`` or
``BINARYMIME`` extensions (see RFC 3030), for instance.
