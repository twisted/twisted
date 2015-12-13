
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Writing a client with Twisted Conch
===================================






Introduction
------------



In the original days of computing, rsh/rlogin were used to connect to
remote computers and execute commands. These commands had the problem
that the passwords and commands were sent in the clear. To solve this
problem, the SSH protocol was created. Twisted Conch implements the
second version of this protocol.

    



Using an SSH Command Endpoint
-----------------------------


    

If your objective is to execute a command on a remote host over an SSH
connection, then the easiest approach may be to
use :api:`twisted.conch.endpoints.SSHCommandClientEndpoint <twisted.conch.endpoints.SSHCommandClientEndpoint>` .
If you haven't used endpoints before, first take a look
at :doc:`the endpoint howto <../../core/howto/endpoints>` to
get an idea of how endpoints work in general.


    



Conch provides an endpoint implementation which establishes an SSH
connection, performs necessary authentication, opens a channel, and
launches a command in that channel.  It then associates the output of that
command with the input of a protocol you supply, and associates output
from that protocol with the input of that command.  Effectively,
this lets you ignore most of the complexity of SSH and just interact with
a remote process as though it were any other stream-oriented connection -
such as TCP or SSL.


    



Conch also provides an endpoint that is initialized with an already
established SSH connection.  This endpoint just opens a new channel on the
existing connection and launches a command in that.


    



Using the ``SSHCommandClientEndpoint`` is about as simple as using any
other stream-oriented client endpoint.  Just create the endpoint defining
where the SSH server to connect to is and a factory defining what kind of
protocol to use to interact with the command and let them get to work
using the endpoint's ``connect`` method.


    



:download:`echoclient_ssh.py <listings/echoclient_ssh.py>`

.. literalinclude:: listings/echoclient_ssh.py



For completeness, this example includes a lot of code to support different
styles of authentication, reading (and possibly updating) existing
*known_hosts* files, and parsing command line options.  Focus on
the latter half of the ``main`` function to see the code that is
most directly responsible for actually doing the necessary SSH connection
setup.  ``SSHCommandClientEndpoint`` accepts quite a few options, since
there is a lot of flexibility in SSH and many possible different server
configurations, but once the endpoint object itself is created, its use is
no more complicated than the use of any other endpoint: pass a factory to
its ``connect`` method and attach a callback to the
resulting ``Deferred`` to do something with the protocol
instance. If you use an endpoint that creates new connections, the connection
attempt can be cancelled by calling ``cancel()`` on this
``Deferred`` .


    



In this case, the connected protocol instance is only used to make the
example wait until the client has finished talking to the server, which
happens after the small amount of example data has been sent to the server
and bounced back by the ``/bin/cat`` process the
protocol is interacting with.


    



Several of the options accepted by ``SSHCommandClientEndpoint.newConnection`` should be easy to understand.
The endpoint takes a reactor which it uses to do any and all I/O it needs to do.
It also takes a command which it executes on the remote server once the SSH connection is established and authenticated; this command is a single string, perhaps including spaces or other special shell symbols, and is interpreted by a shell on the server.
It takes a username with which it identifies itself to the server for authentication purposes.
It takes an optional password argument which will also be used for authentication - if the server supports password authentication (prefer keys instead where possible, see below).
It takes a host (either a name or an IP address) and a port number, defining where to connect.


    



Some of the other options may bear further explanation.


    



The ``keys`` argument gives any SSH :api:`twisted.conch.ssh.keys.Key <Key>` objects which may be useful for authentication.
These keys are available to the endpoint for authentication, but only keys that the server indicates are useful will actually be used.
This argument is optional.
If key authentication against the server is either unnecessary or undesired, it may be omitted entirely.


    



The ``agentEndpoint`` argument gives the ``SSHCommandClientEndpoint`` an opportunity to connect to an SSH authentication agent.
The agent may already be loaded with keys, or may have some other way to authenticate a connection.
Using the agent can mean the process actually establishing the SSH connection doesn't need to load any authentication material (passwords or keys) itself (often convenient in case keys are encrypted and potentially more secure, since only the agent process ever actually holds the secrets).
The value for this argument is another ``IStreamClientEndpoint`` .
Often in a typical *NIX desktop environment, the *SSH_AUTH_SOCK* environment variable will give the location of a AF_UNIX socket.
This explains the value ``echoclient_ssh.py`` assigns this parameter when *--no-agent* is not given.


    



The ``knownHosts`` argument accepts a :api:`twisted.conch.client.knownhosts.KnownHostsFile <KnownHostsFile>` instance and controls how server keys are checked and stored.
This object has the opportunity to reject server keys if they differ from expectations.
It can also save server keys when they are first observed.


    



Finally, there is one option that is not demonstrated in the example - the ``ui`` argument.
This argument is closely related to the ``knownHosts`` argument described above.
``KnownHostsFile`` may require user-input under certain circumstances - for example, to ask if it should accept a server key the first time it is observed.
The ``ui`` object is how this user-input is obtained.
By default, a :api:`twisted.conch.client.knownhosts.ConsoleUI <ConsoleUI>` instance associated with */dev/tty* will be used.
This gives about the same behavior as is seen in a standard command-line ssh client.
See :api:`twisted.conch.endpoints.SSHCommandClientEndpoint.newConnection <SSHCommandClientEndpoint.newConnection>` for details about how edge cases are handled for this default value.
For use of ``SSHCommandClientEndpoint`` that is intended to be completely autonomous, applications will probably want to specify a custom ``ui`` object which can make the necessary decisions without user-input.


    



It is also possible to run commands (one or more) over an
already-established connection.  This is done using the alternate
constructor ``SSHCommandClientEndpoint.existingConnection`` .


    



:download:`echoclient_shared_ssh.py <listings/echoclient_shared_ssh.py>`

.. literalinclude:: listings/echoclient_shared_ssh.py



Writing a client
----------------




In case the endpoint is missing some necessary functionality, or in case you
want to interact with a different part of an SSH server - such as one of
its *subsystems* (for example, SFTP), you may need to use the
lower-level Conch client interface.  This is described below.




Writing a client with Conch involves sub-classing 4 classes: :api:`twisted.conch.ssh.transport.SSHClientTransport <twisted.conch.ssh.transport.SSHClientTransport>` , :api:`twisted.conch.ssh.userauth.SSHUserAuthClient <twisted.conch.ssh.userauth.SSHUserAuthClient>` , :api:`twisted.conch.ssh.connection.SSHConnection <twisted.conch.ssh.connection.SSHConnection>` , and :api:`twisted.conch.ssh.channel.SSHChannel <twisted.conch.ssh.channel.SSHChannel>` . We'll start out
with ``SSHClientTransport`` because it's the base 
of the client.





The Transport
-------------




.. code-block:: python

    
    from twisted.conch import error
    from twisted.conch.ssh import transport
    from twisted.internet import defer
    
    class ClientTransport(transport.SSHClientTransport):
    
        def verifyHostKey(self, pubKey, fingerprint):
            if fingerprint != 'b1:94:6a:c9:24:92:d2:34:7c:62:35:b4:d2:61:11:84':
                return defer.fail(error.ConchError('bad key'))
            else:
                return defer.succeed(1)
    
        def connectionSecure(self):
            self.requestService(ClientUserAuth('user', ClientConnection()))




See how easy it is? ``SSHClientTransport`` 
handles the negotiation of encryption and the verification of keys
for you. The one security element that you as a client writer need to
implement is ``verifyHostKey()`` . This method
is called with two strings: the public key sent by the server and its
fingerprint. You should verify the host key the server sends, either
by checking against a hard-coded value as in the example, or by asking
the user. ``verifyHostKey`` returns a :api:`twisted.internet.defer.Deferred <twisted.internet.defer.Deferred>` which gets a callback
if the host key is valid, or an errback if it is not. Note that in the
above, replace 'user' with the username you're attempting to ssh with,
for instance a call to ``os.getlogin()`` for the
current user.




The second method you need to implement is ``connectionSecure()`` . It is called when the
encryption is set up and other services can be run. The example requests
that the ``ClientUserAuth`` service be started.
This service will be discussed next.





The Authorization Client
------------------------




.. code-block:: python

    
    from twisted.conch.ssh import keys, userauth
    
    # these are the public/private keys from test_conch
    
    publicKey = 'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3\
    /c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHR\
    ivcJSkbh/C+BR3utDS555mV'
    
    privateKey = """-----BEGIN RSA PRIVATE KEY-----
    MIIByAIBAAJhAK8ycfDmDpyZs3+LXwRLy4vA1T6yd/3PZNiPwM+uH8Yx3/YpskSW
    4sbUIZR/ZXzY1CMfuC5qyR+UDUbBaaK3Bwyjk8E02C4eSpkabJZGB0Yr3CUpG4fw
    vgUd7rQ0ueeZlQIBIwJgbh+1VZfr7WftK5lu7MHtqE1S1vPWZQYE3+VUn8yJADyb
    Z4fsZaCrzW9lkIqXkE3GIY+ojdhZhkO1gbG0118sIgphwSWKRxK0mvh6ERxKqIt1
    xJEJO74EykXZV4oNJ8sjAjEA3J9r2ZghVhGN6V8DnQrTk24Td0E8hU8AcP0FVP+8
    PQm/g/aXf2QQkQT+omdHVEJrAjEAy0pL0EBH6EVS98evDCBtQw22OZT52qXlAwZ2
    gyTriKFVoqjeEjt3SZKKqXHSApP/AjBLpF99zcJJZRq2abgYlf9lv1chkrWqDHUu
    DZttmYJeEfiFBBavVYIF1dOlZT0G8jMCMBc7sOSZodFnAiryP+Qg9otSBjJ3bQML
    pSTqy7c3a2AScC/YyOwkDaICHnnD3XyjMwIxALRzl0tQEKMXs6hH8ToUdlLROCrP
    EhQ0wahUTCk1gKA4uPD6TMTChavbh4K63OvbKg==
    -----END RSA PRIVATE KEY-----"""
    
    class ClientUserAuth(userauth.SSHUserAuthClient):
    
        def getPassword(self, prompt = None):
            return 
            # this says we won't do password authentication
    
        def getPublicKey(self):
            return keys.Key.fromString(data = publicKey).blob()
    
        def getPrivateKey(self):
            return defer.succeed(keys.Key.fromString(data = privateKey).keyObject)




Again, fairly simple. The ``SSHUserAuthClient`` takes care of most
of the work, but the actual authentication data needs to be
supplied. ``getPassword()`` asks for a
password, ``getPublicKey()`` and ``getPrivateKey()`` get public and private keys,
respectively. ``getPassword()`` returns
a ``Deferred`` that is called back with
the password to use.

``getPublicKey()`` returns the SSH key data for the public key to use.
:api:`Key <twisted.conch.ssh.keys.Key.fromString()>` will take a key in OpenSSH, LSH or any supported format, as a string, and generate a new :api:`Key <twisted.conch.ssh.keys.Key>`.
Alternatively, ``keys.Key.fromFile()`` can be used instead, which
will take the filename of a key in the supported format, and  and generate a new  :api:`Key <twisted.conch.ssh.keys.Key>`.

``getPrivateKey()`` returns a ``Deferred`` which is called back with the private :api:`Key <twisted.conch.ssh.keys.Key>`.

``getPassword()`` and ``getPrivateKey()`` return ``Deferreds`` because they may need to ask the user for input.

Once the authentication is complete, ``SSHUserAuthClient`` takes care of starting the code ``SSHConnection`` object given to it. Next, we'll
look at how to use the ``SSHConnection``





The Connection
--------------




.. code-block:: python

    
    from twisted.conch.ssh import connection
    
    class ClientConnection(connection.SSHConnection):
    
        def serviceStarted(self):
            self.openChannel(CatChannel(conn = self))




``SSHConnection`` is the easiest,
as it's only responsible for starting the channels. It has
other methods, those will be examined when we look at ``SSHChannel`` .





The Channel
-----------




.. code-block:: python

    
    from twisted.conch.ssh import channel, common
    
    class CatChannel(channel.SSHChannel):
    
        name = 'session'
    
        def channelOpen(self, data):
            d = self.conn.sendRequest(self, 'exec', common.NS('cat'),
                                      wantReply = 1)
            d.addCallback(self._cbSendRequest)
            self.catData = ''
    
        def _cbSendRequest(self, ignored):
            self.write('This data will be echoed back to us by "cat."\r\n')
            self.conn.sendEOF(self)
            self.loseConnection()
    
        def dataReceived(self, data):
            self.catData += data
    
        def closed(self):
            print 'We got this from "cat":', self.catData




Now that we've spent all this time getting the server and
client connected, here is where that work pays off. ``SSHChannel`` is the interface between you and the
other side. This particular channel opens a session and plays with the
'cat' program, but your channel can implement anything, so long as the
server supports it.




The ``channelOpen()`` method is
where everything gets started. It gets passed a chunk of data;
however, this chunk is usually nothing and can be ignored.
Our ``channelOpen()`` initializes our
channel, and sends a request to the other side, using the ``sendRequest()`` method of the ``SSHConnection`` object. Requests are used to send
events to the other side. We pass the method self so that it knows to
send the request for this channel. The 2nd argument of 'exec' tells the
server that we want to execute a command. The third argument is the data
that accompanies the request. :api:`twisted.conch.ssh.common.NS <common.NS>` encodes
the data as a length-prefixed string, which is how the server expects
the data. We also say that we want a reply saying that the process has a
been started. ``sendRequest()`` then returns a ``Deferred`` which we add a callback for.




Once the callback fires, we send the data. ``SSHChannel`` supports the :api:`twisted.internet.interfaces.ITransport <twisted.internet.interfaces.ITransport>` 
interface, so
it can be given to Protocols to run them over the secure
connection. In our case, we just write the data directly. ``sendEOF()`` does not follow the interface,
but Conch uses it to tell the other side that we will write no
more data. ``loseConnection()`` shuts
down our side of the connection, but we will still receive data
through ``dataReceived()`` . The ``closed()`` method is called when both sides of the
connection are closed, and we use it to display the data we received
(which should be the same as the data we sent.)




Finally, let's actually invoke the code we've set up.





The main() function
-------------------



.. code-block:: python

    
    from twisted.internet import protocol, reactor
    
    def main():
        factory = protocol.ClientFactory()
        factory.protocol = ClientTransport
        reactor.connectTCP('localhost', 22, factory)
        reactor.run()
    
    if __name__ == "__main__":
        main()




We call ``connectTCP()`` to connect to
localhost, port 22 (the standard port for ssh), and pass it an instance
of :api:`twisted.internet.protocol.ClientFactory <twisted.internet.protocol.ClientFactory>` .
This instance has the attribute ``protocol`` 
set to our earlier ``ClientTransport`` 
class. Note that the protocol attribute is set to the class ``ClientTransport`` , not an instance of ``ClientTransport`` ! When the ``connectTCP`` call completes, the protocol will be
called to create a ``ClientTransport()`` object
- this then invokes all our previous work.




It's worth noting that in the example ``main()`` 
routine, the ``reactor.run()`` call never returns. 
If you want to make the program exit, call ``reactor.stop()`` in the earlier ``closed()`` method.




If you wish to observe the interactions in more detail, adding a call
to ``log.startLogging(sys.stdout, setStdout=0)`` 
before the ``reactor.run()`` call will send all
logging to stdout.



