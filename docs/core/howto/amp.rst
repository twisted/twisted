
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$



**A** synchronous **M** essaging **P** rotocol Overview



**A** synchronous **M** essaging **P** rotocol Overview
The purpose of this guide is to describe the uses for and usage of :api:`twisted.protocols.amp <twisted.protocols.amp>` beyond what is explained in the API documentation.  It will show you how to implement an AMP server which can respond to commands or interact directly with individual messages.  It will also show you how to implement an AMP client which can issue commands to a server.

    


AMP is a bidirectional command/response-oriented protocol intended to be extended with application-specific request types and handlers.  Various simple data types are supported and support for new data types can be added by applications.

    



Setting Up
----------


    
AMP runs over a stream-oriented connection-based protocol, such as TCP or SSL.  Before you can use any features of the AMP protocol, you need a connection.  The protocol class to use to establish an AMP connection is :api:`twisted.protocols.amp.AMP <AMP>` .  Connection setup works as it does for almost all protocols in Twisted.  For example, you can set up a listening AMP server using a server endpoint:

    



:download:`basic_server.tac <listings/amp/basic_server.tac>`

.. literalinclude:: listings/amp/basic_server.tac


And you can connect to an AMP server using a client endpoint:

    



:download:`basic_client.py <listings/amp/basic_client.py>`

.. literalinclude:: listings/amp/basic_client.py



Commands
--------


    
Either side of an AMP connection can issue a command to the other side.  Each kind of command is represented as a subclass of :api:`twisted.protocols.amp.Command <Command>` .  A ``Command`` defines arguments, response values, and error conditions.

    



.. code-block:: python

    from twisted.protocols.amp import Integer, String, Unicode, Command
    
    class UsernameUnavailable(Exception):
        pass
    
    class RegisterUser(Command):
        arguments = [('username', Unicode()),
                     ('publickey', String())]
    
        response = [('uid', Integer())]
    
        errors = {UsernameUnavailable: 'username-unavailable'}



    
The definition of the command's signature - its arguments, response, and possible error conditions - is separate from the implementation of the behavior to execute when the command is received.  The ``Command`` subclass only defines the former.

    


Commands are issued by calling ``callRemote`` on either side of the connection.  This method returns a ``Deferred`` which eventually fires with the result of the command.

    



:download:`command_client.py <listings/amp/command_client.py>`

.. literalinclude:: listings/amp/command_client.py



Locators
--------



    
The logic for handling a command can be specified as an object separate from the ``AMP`` instance which interprets and formats bytes over the network.

    



.. code-block:: python

    from twisted.protocols.amp import CommandLocator
    from twisted.python.filepath import FilePath
    
    class UsernameUnavailable(Exception):
        pass
    
    class UserRegistration(CommandLocator):
        uidCounter = 0
    
        @RegisterUser.responder
        def register(self, username, publickey):
            path = FilePath(username)
            if path.exists():
                raise UsernameUnavailable()
            self.uidCounter += 1
            path.setContent('%d %s\n' % (self.uidCounter, publickey))
            return self.uidCounter



    
When you define a separate ``CommandLocator`` subclass, use it by passing an instance of it to the ``AMP`` initializer.

    



.. code-block:: python

    factory = Factory()
    factory.protocol = lambda: AMP(locator=UserRegistration())



    
If no locator is passed in, ``AMP`` acts as its own locator.  Command responders can be defined on an ``AMP`` subclass, just as the responder was defined on the ``UserRegistration`` example above.

    



Box Receivers
-------------


    
AMP conversations consist of an exchange of messages called *boxes* .  A *box* consists of a sequence of pairs of key and value (for example, the pair ``username`` and ``alice`` ).  Boxes are generally represented as ``dict`` instances.  Normally boxes are passed back and forth to implement the command request/response features described above.  The logic for handling each box can be specified as an object separate from the ``AMP`` instance.

    



.. code-block:: python

    from zope.interface import implements
    
    from twisted.protocols.amp import IBoxReceiver
    
    class BoxReflector(object):
        implements(IBoxReceiver)
    
        def startReceivingBoxes(self, boxSender):
            self.boxSender = boxSender
    
        def ampBoxReceived(self, box):
            self.boxSender.sendBox(box)
    
        def stopReceivingBoxes(self, reason):
            self.boxSender = None



    
These methods parallel those of ``IProtocol`` .  Startup notification is given by ``startReceivingBoxes`` .  The argument passed to it is an ``IBoxSender`` provider, which can be used to send boxes back out over the network.  ``ampBoxReceived`` delivers notification for a complete box having been received.  And last, ``stopReceivingBoxes`` notifies the object that no more boxes will be received and no more can be sent.  The argument passed to it is a ``Failure`` which may contain details about what caused the conversation to end.

    


To use a custom ``IBoxReceiver`` , pass it to the ``AMP`` initializer.

    



.. code-block:: python

    factory = Factory()
    factory.protocol = lambda: AMP(boxReceiver=BoxReflector())



    
If no box receiver is passed in, ``AMP`` acts as its own box receiver.  It handles boxes by treating them as command requests or responses and delivering them to the appropriate responder or as a result to a ``callRemote`` ``Deferred`` .

  

