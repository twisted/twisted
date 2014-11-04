
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Access Logging
==============

As long as we're on the topic of :doc:`logging <logging-errors>`\ , this is probably a good time to mention Twisted Web's access log support.
In this example, we'll see what Twisted Web logs for each request it processes and how this can be customized.

If you've run any of the previous examples and watched the output of ``twistd`` or read ``twistd.log`` then you've already seen some log lines like this:

  2014-01-29 17:50:50-0500 [HTTPChannel,0,127.0.0.1] "127.0.0.1" - - [29/Jan/2014:22:50:50 +0000] "GET / HTTP/1.1" 200 2753 "-" "Mozilla/5.0 ..."

If you focus on the latter portion of this log message you'll see something that looks like a standard "combined log format" message.
However, it's prefixed with the normal Twisted logging prefix giving a timestamp and some protocol and peer addressing information.
Much of this information is redundant since it is part of the combined log format.
:api:`twisted.web.server.Site <Site>` lets you produce a more compact log which omits the normal Twisted logging prefix.
To take advantage of this feature all that is necessary is to tell :api:`twisted.web.server.Site <Site>` where to write this compact log.
Do this by passing ``logPath`` to the initializer:

.. code-block:: python

    ...
    factory = Site(root, logPath=b"/tmp/access-logging-demo.log")

Or if you want to change the logging behavior of a server you're launching with ``twistd web`` then just pass the ``--logfile`` option:

.. code-block:: shell

    $ twistd -n web --logfile /tmp/access-logging-demo.log

Apart from this, the rest of the server setup is the same.
Once you pass ``logPath`` or use ``--logfile`` on the command line the server will produce a log file containing lines like:

  "127.0.0.1" - - [30/Jan/2014:00:13:35 +0000] "GET / HTTP/1.1" 200 2753 "-" "Mozilla/5.0 ..."

Any tools expecting combined log format messages should be able to work with these log files.

:api:`twisted.web.server.Site <Site>` also allows the log format used to be customized using its ``logFormatter`` argument.
Twisted Web comes with one alternate formatter, :api:`twisted.web.http.proxiedLogFormatter <proxiedLogFormatter>`, which is for use behind a proxy that sets the ``X-Forwarded-For`` header.
It logs the client address taken from this header rather than the network address of the client directly connected to the server.
Here's the complete code for an example that uses both these features:

.. code-block:: python

    from twisted.web.http import proxiedLogFormatter
    from twisted.web.server import Site
    from twisted.web.static import File
    from twisted.internet import reactor

    resource = File('/tmp')
    factory = Site(resource, logPath=b"/tmp/access-logging-demo.log", logFormatter=proxiedLogFormatter)
    reactor.listenTCP(8888, factory)
    reactor.run()
