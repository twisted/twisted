:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Communicating With IRC Clients
==============================

Communicating with clients is the whole point of an IRC server, so you want to make sure you're doing it properly.
Today, we'll be looking at receiving messages from a client and sending messages to the client.


Representing Clients in Twisted
-------------------------------

Users in Twisted IRC are represented as subclasses of :api:`twisted.words.protocols.irc.IRC <the IRC class>`.
This works as the protocol for your Factory class. It will also give you IRC features (like automatically parsing incoming lines) without you having to implement them yourself. The rest of this guide assumes this setup.


Sending Messages
----------------

Messages are sent to users using the user object's :api:`twisted.words.protocols.irc.IRC.sendMessage <sendMessage>` method.


Sending Basic Messages
~~~~~~~~~~~~~~~~~~~~~~

The basic syntax for sending messages to users is
as follows:

.. code-block:: python

    user.sendCommand("COMMAND", (param1, param2), server.name)

The prefix keyword argument is optional, and it may be omitted to send a message without a prefix (for example, the ERROR command).
The command is whatever command you plan to send, e.g. "PRIVMSG", "MODE", etc.
All arguments following the command are the parameters you want to send for the command.
If the last argument needs to be prefixed with a colon (because it has spaces in it, e.g. a PRIVMSG message), you must add the colon to the beginning of the parameter yourself. For example:
.. code-block:: python

    user.sendCommand("PRIVMSG", (user.nickname, ":{}".format(message)), sendingUser.hostmask)


Sending Messages with Tags
~~~~~~~~~~~~~~~~~~~~~~~~~~
Twisted also allows sending message tags as specified in
`IRCv3 <https://ircv3.net/specs/core/message-tags-3.2.html>`__.

Let's say, for example, that your server has a feature to play back a little bit of previous channel content when someone joins a channel.
You want a way to tell people when this message occurred.  The best way to provide this information is through the `server-time specification <http://ircv3.net/specs/extensions/server-time-3.2.html>`__.

Let's say you're storing past messages in a channel object in some structure like this:

.. code-block:: python

    channel.pastMessages = [
        ("I sent some text!", "author!ident@host", datetime object representing the when the message was sent),
        ("I did, too!", "someone-else!ident@host", another datetime object)
    ]

Your actual implementation may vary. I went with something simple here. The times of the messages would be generated using something like ``datetime.utcnow()`` when the message was received.

Tags are passed as a list of tuples. If you're sending a number of tags, you may have an existing tag dictionary. You can simply add to it (assuming ``message`` is the loop variable for channel.pastMessages above):

.. code-block:: python

    sendingTags["server-time"] = "{}Z".format(message[2].isoformat()[:-3])

This will generate the required time format and add it to the tag dictionary. The last three characters that we remove are the microseconds; removing the last three digits changes the precision to milliseconds.

Once your tags are collected, you can send the message. The tag dictionary is passed using the ``tags`` argument (in the same loop as above):

.. code-block:: python

    user.sendCommand("PRIVMSG", (user.nickname, message[0]), message[1], sendingTags)


Receiving Messages
------------------
Twisted Words will handle receiving messages and parsing lines into tokens. The parsed messages are passed into your command through the user's :api:`twisted.words.protocols.irc.IRC.handleCommand <handleCommand>` method.


Handling Commands
~~~~~~~~~~~~~~~~~
The default IRC handleCommand method calls the ``irc_COMMAND`` method when it receives the command ``COMMAND``, and it calls irc_unknown if the method for the command received isn't defined.

.. code-block:: python
    
    from twisted.words.protocols import irc
    
    class IRCUser(irc.IRC):
        # possibly other definitions here
        def irc_unknown(self, prefix, command, params):
            self.sendCommand(irc.ERR_UNKNOWNCOMMAND, (command, ":Unknown command"), server.name)
        
        def irc_PRIVMSG(self, prefix, params):
            # do some stuff to handle PRIVMSG for your server's setup
        
        # lots of other command definitions

If you have a server setup that doesn't allow you to do this (e.g. a modular server program), you may, of course, override the handleCommand function to route commands to your own handlers.


Receiving Messages with Tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This has not yet been implemented.