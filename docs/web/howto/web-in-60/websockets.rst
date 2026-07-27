:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

WebSockets
==========

Twisted Web provides support for the WebSocket protocol for clients (such as web browsers) to connect to resources and receive bi-directional communication with the server.

For the purposes of our example here, you will need to have some familiarity with the concepts covered in :doc:`serving static content <static-content>` and :doc:`rpy scripts <rpy-scripts>`, because we will be using those to construct our resource hierarchy.

.. note::

   In order to use the websocket support in Twisted, you will need the ``websocket`` optional dependency, so :doc:`install Twisted </installation>` with either ``pip install twisted[websocket]`` or install one that includes it, such as ``twisted[all_non_platform]`` or ``twisted[all]`` .

WebSocket Server
----------------

Let's use Twisted to create a simple websocket server, and then build a web-browser based client to communicate with it.

To begin with, we will need a folder with 3 files in it.
First, let's do the Twisted part.  We need a :py:class:`twisted.web.websocket.WebSocketResource` to be served at a known URL, so let's put one into a ``.rpy`` file called ``websocket-server.rpy`` :

:download:`websocket-server.rpy <../../examples/websocket/websocket-server.rpy>`

.. literalinclude:: ../../examples/websocket/websocket-server.rpy
   :language: python

Note that by using a ``@classmethod`` for ``buildProtocol``, the *type* of  ``WebSocketDemo`` complies with the :py:class:`twisted.web.websocket.WebSocketServerFactory` :py:class:`protocol <typing.Protocol>`, returning a ``WebSocketDemo`` that complies with :py:class:`twisted.web.websocket.WebSocketProtocol` ; we can then pass the type of ``WebSocketDemo`` itself, without instantiating it, to :py:class:`twisted.web.websocket.WebSocketResource`.
We implement ``negotiationFinished``, the method called once the websocket connection is fully set up, to begin sending a text message to our peer once per second.

Then, we will need an index page for our live websocket site, with a button on it that hooks up a JavaScript function to connect to ``/websocket-server.rpy``:

:download:`index.html <../../examples/websocket/index.html>`

.. literalinclude:: ../../examples/websocket/index.html
   :language: html

Finally, we need our JavaScript source code that actually does the connecting of various events.
Learning how to program in JavaScript, or even the entire JavaScript WebSocket API, is a bit outside the scope of this tutorial.
You can read more about WebSocket JavaScript API at the `MDN WebSocket documentation <https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_client_applications>`_\ .
Hopefully this minimal example is clear:

:download:`websocket-browser-client.js <../../examples/websocket/websocket-browser-client.js>`

.. literalinclude:: ../../examples/websocket/websocket-browser-client.js
   :language: js

We define a function, ``doConnect``, that the button in our HTML example above will call, which:

1. creates a new websocket that will connect to the URL ``ws://localhost:8080/websocket-server.rpy`` .
2. adds an event handler to that websocket for when it connects, to send a message to the server,
3. and also adds event handlers for when the connection receives a text message, an error, or a closure from the peer, to display those events to the user.

If you were to put these all into a folder called ``my-websocket-demo`` , you can use ``twist`` to serve them, via ``twist web --path ./my-websocket-demo``.
Then, you can open up a web browser, pointed at ``http://localhost:8080/`` and see a "connect websocket" button.
Click the button, and you should see the web page populate with text like this:

.. code-block::

   socket opened: «{"isTrusted":true}»
   message received: «heartbeat 1»
   message received: «reply to hello world»
   message received: «heartbeat 2»
   message received: «heartbeat 3»
   message received: «heartbeat 4»

And that's all you need to implement a websocket server with Twisted!

Since :py:class:`twisted.web.websocket.WebSocketResource` is a standard Twisted :py:class:`resource <twisted.web.server.Resource>`, you can integrate it with things like :doc:`authentication <http-auth>` or :doc:`sessions <session-basics>`, just as you would any other resource.

WebSocket Client
----------------

Of course, if we have a server, we may also want to talk to it from our Twisted applications.
To do that, let's build a simple websocket client, with :py:class:`twisted.web.websocket.WebSocketClientEndpoint`.
This client could talk to **any** WebSocket server, regardless of how it was implemented, but since we just built one with Twisted, we'll use that one.
It looks much the same as the server, but, we will just print out each data message we receive.

.. note::

   In this example, we use the ``ws://`` protocol which indicates a plain-text websocket connection.
   Obtaining a valid HTTPS certificate for your local example goes a bit beyond the scope of this tutorial, but you can test using the ``wss://`` protocol, as well as testing against a non-Twisted server, by substituting the URL ``"wss://echo.websocket.org/"`` in the client demo.
   Make sure to also install the ``[tls]`` :ref:`optional dependency group <Optional Dependencies>` to install the required dependencies for Twisted's HTTPS client.

:download:`websocket-client.py <../../examples/websocket/websocket-client.py>`

.. literalinclude:: ../../examples/websocket/websocket-client.py
   :language: python

If you leave the same server running, the one you just tested with your browser, and then run this example, you should see something like this:

.. code-block::

   connecting...
   connected!
   received text: 'heartbeat 1'
   received text: 'reply to hello, world!'
   received text: 'heartbeat 2'
   received text: 'heartbeat 3'
   received text: 'heartbeat 4'
   received text: 'heartbeat 5'
   received text: 'heartbeat 6'
   received text: 'heartbeat 7'
   received text: 'heartbeat 8'
   received text: 'heartbeat 9'
   received text: 'heartbeat 10'
   received text: 'heartbeat 11'

And now you have a functioning WebSocket server and client using Twisted!
