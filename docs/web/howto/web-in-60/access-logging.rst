Access Logging
==============

As long as we're on the topic of :doc:`logging <logging-errors>`\ , this is probably a good time to mention Twisted Web's access log support.
In this example, we'll see what Twisted Web logs for each request it processes and how this can be customized.

If you've run any of the previous examples and watched the output of ``twistd`` or read ``twistd.log`` then you've already seen some log lines like this:

  2017-05-23T15:48:11-0700 [twisted.web.server#info] "127.0.0.1" - "GET / HTTP/1.1" 200 111 "-" "Mozilla/5.0 ..."

If you focus on the latter portion of this log message you'll see something that looks like a standard "combined log format" message.
However, it's prefixed with the normal Twisted logging prefix giving a timestamp and some protocol and peer addressing information.
Much of this information is redundant since it is part of the combined log format.
:api:`twisted.web.server.makeCombinedLogFormatFileForServer <makeCombinedLogFormatFileForServer>` lets you produce a more compact log which omits the normal Twisted logging prefix.
To output this format, pass the Server you create to ``makeCombinedLogFormatFileForServer`` with a file-like object opened in binary mode:

.. code-block:: python

    from twisted.python import logfile
    from twisted.web.server import makeServer, makeCombinedLogFormatFileForServer
    factory = makeServer(root)
    log = logfile.LogFile(b"/tmp/", b"access-logging-demo.log")
    makeCombinedLogFormatFileForServer(factory, log)

Or if you want to change the logging behavior of a server you're launching with ``twist web`` then just pass the ``--logfile`` option:

.. code-block:: shell

    $ twist web --logfile /tmp/access-logging-demo.log

Apart from this, the rest of the server setup is the same.
If you use either of these options, the server will produce a log file containing lines like:

  127.0.0.1 - - [23/May/2017:18:46:53 +0000] "GET / HTTP/1.1" 200 111 "-" "Mozilla/5.0 ..."

Any tools expecting combined log format messages should be able to work with these log files.
