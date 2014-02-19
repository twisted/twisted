:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Deploying Twisted with systemd
==============================

Introduction
------------
In this tutorial you will learn how to start a Twisted service using ``systemd``\ .
You will also learn how to start the service using ``socket activation``\ .

.. note::

   The examples in this tutorial demonstrate how to launch a Twisted web server, but the same techniques apply to any Twisted service.

Prerequisites
-------------
Twisted

  You will need a version of Twisted >= 12.2 for the socket activation section of this tutorial.

  This tutorial was written on a Fedora 18 Linux operating system with a system wide installation of Twisted and Twisted Web.

  If you have installed Twisted locally eg in your home directory or in a virtualenv, you will need to modify the paths in some of the following examples.

  Test your Twisted installation by starting a ``twistd web`` server on TCP port 8080 with the following command:

  .. code-block:: console

      $ twistd --nodaemon web --port 8080 --path /srv/www/www.example.com/static
      2013-01-28 13:21:35+0000 [-] Log opened.
      2013-01-28 13:21:35+0000 [-] twistd 12.3.0 (/usr/bin/python 2.7.3) starting up.
      2013-01-28 13:21:35+0000 [-] reactor class: twisted.internet.epollreactor.EPollReactor.
      2013-01-28 13:21:35+0000 [-] Site starting on 8080
      2013-01-28 13:21:35+0000 [-] Starting factory <twisted.web.server.Site instance at 0x7f57eb66efc8>

  This assumes that you have the following static web page in the following directory structure:

  .. code-block:: console

      # tree /srv/
      /srv/
      └── www
          └── www.example.com
              └── static
                  └── index.html

  ::

      <!doctype html>
      <html lang=en>
        <head>
          <meta charset=utf-8>
          <title>Example Site</title>
        </head>
        <body>
          <h1>Example Site</h1>
        </body>
      </html>

  Now try connecting to `http://localhost:8080 <http://localhost:8080>`_ in your web browser.

  If you do not see your web page or if ``twistd`` didn't start, you should investigate and fix the problem before continuing.

Basic Systemd Service Configuration
-----------------------------------
The essential configuration file for a ``systemd`` service is the `service <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_ file.

Later in this tutorial, you will learn about some other types of configuration file, which are used to control when and how your service is started.

But we will begin by configuring ``systemd`` to start a Twisted web server immediately on system boot.

Create a systemd.service file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create the `service <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_ file at ``/etc/systemd/system/www.example.com.service`` with the following content:

:download:`/etc/systemd/system/www.example.com.service <listings/systemd/www.example.com.static.service>`

.. literalinclude:: listings/systemd/www.example.com.static.service
   :language: ini

This configuration file contains the following note worthy directives:

ExecStart

  Always include the full path to ``twistd`` in case you have multiple versions installed.

  The ``--nodaemon`` flag makes ``twistd`` run in the foreground.
  Systemd works best with child processes that remain in the foreground.

  The ``--pidfile=`` flag prevents ``twistd`` from writing a pidfile.
  A pidfile is not necessary when Twisted runs as a foreground process.

  The ``--path`` flag specifies the location of the website files.
  In this example we use "." which makes ``twistd`` serve files from its current working directory (see below).

WorkingDirectory

  Systemd can configure the working environment of its child processes.

  In this example the working directory of ``twistd`` is set to that of the static website.

User / Group

  Systemd can also control the effective user and group of its child processes.

  This example uses an un-privileged user "nobody" and un-privileged group "nobody".

  This is an important security measure which ensures that the Twisted sub-process can not access restricted areas of the file system.

Restart

  Systemd can automatically restart a child process if it exits or crashes unexpectedly.

  In this example the ``Restart`` option is set to ``always``\ , which ensures that ``twistd`` will be restarted under all circumstances.

WantedBy

  Systemd service dependencies are controlled by ``WantedBy`` and ``RequiredBy`` directives in the ``[Install]`` section of configuration file.

  The special `multi-user.target <http://www.freedesktop.org/software/systemd/man/systemd.special.html#multi-user.target>`_ is used in this example so that ``systemd`` starts the ``twistd web`` service when it reaches the multi-user stage of the boot sequence.

There are many more service directives which are documented in the `systemd.directives man page <http://www.freedesktop.org/software/systemd/man/systemd.directives.html>`_.

Reload ``systemd``
~~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ sudo systemctl daemon-reload

This forces ``systemd`` to read the new configuration file.

Always run ``systemctl daemon-reload`` after changing any of the ``systemd`` configuration files.

Start the service
~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ sudo systemctl start www.example.com

``twistd`` should now be running and listening on TCP port 8080. You can verify this using the ``systemctl status`` command. eg

.. code-block:: console

    $ systemctl status www.example.com.service
    www.example.com.service - Example Web Server
              Loaded: loaded (/etc/systemd/system/www.example.com.service; enabled)
              Active: active (running) since Mon 2013-01-28 16:16:26 GMT; 1s ago
            Main PID: 10695 (twistd)
              CGroup: name=systemd:/system/www.example.com.service
                      └─10695 /usr/bin/python /usr/bin/twistd --nodaemon --pidfile= web --port 8080 --path .

    Jan 28 16:16:26 zorin.lan systemd[1]: Starting Example Web Server...
    Jan 28 16:16:26 zorin.lan systemd[1]: Started Example Web Server.
    Jan 28 16:16:26 zorin.lan twistd[10695]: 2013-01-28 16:16:26+0000 [-] Log opened.
    Jan 28 16:16:26 zorin.lan twistd[10695]: 2013-01-28 16:16:26+0000 [-] twistd 12.1.0 (/usr/bin/python 2.7.3) starting up.
    Jan 28 16:16:26 zorin.lan twistd[10695]: 2013-01-28 16:16:26+0000 [-] reactor class: twisted.internet.epollreactor.EPollReactor.
    Jan 28 16:16:26 zorin.lan twistd[10695]: 2013-01-28 16:16:26+0000 [-] Site starting on 8080
    Jan 28 16:16:26 zorin.lan twistd[10695]: 2013-01-28 16:16:26+0000 [-] Starting factory <twisted.web.server.Site instance at 0x159b758>

The ``systemctl status`` command is convenient because it shows you both the current status of the service and a short log of the service output.

This is especially useful for debugging and diagnosing service startup problems.

The ``twistd`` subprocess will log messages to ``stderr`` and ``systemd`` will log these messages to syslog.
You can verify this by monitoring the syslog messages or by using the new ``journalctl`` tool in Fedora.

See the `systemctl man page <http://www.freedesktop.org/software/systemd/man/systemctl.html>`_ for details of other ``systemctl`` command line options.

Enable the service
~~~~~~~~~~~~~~~~~~
We've seen how to start the service manually, but now we need to "enable" it so that it starts automatically at boot time.

Enable the service with the following command:

.. code-block:: console

    $ sudo systemctl enable www.example.com.service
    ln -s '/etc/systemd/system/www.example.com.service' '/etc/systemd/system/multi-user.target.wants/www.example.com.service'

This creates a symlink to the service file in the ``multi-user.target.wants`` directory.

The Twisted web server will now be started automatically at boot time.

The ``multi-user.target`` is an example of a `"special" systemd unit <http://www.freedesktop.org/software/systemd/man/systemd.special.html>`_.
Later in this tutorial you will learn how to use another special unit - the ``sockets.target``\ .

Test that the service is automatically restarted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``Restart=always`` option in the ``systemd.service`` file ensures that ``systemd`` will restart the ``twistd`` process if and when it exits unexpectedly.

You can read about other ``Restart`` options in the `systemd.service man page <http://www.freedesktop.org/software/systemd/man/systemd.service.html>`_.

Try killing the ``twistd`` process and then checking its status again:

.. code-block:: console

    $ sudo kill 12543

    $ systemctl status www.example.com.service
    www.example.com.service - Example Web Server
              Loaded: loaded (/etc/systemd/system/www.example.com.service; disabled)
              Active: active (running) since Mon 2013-01-28 17:47:37 GMT; 1s ago
            Main PID: 12611 (twistd)

The "Active" time stamp shows that the ``twistd`` process was restarted within 1 second.

Now stop the service before you proceed to the next section.

.. code-block:: console

    $ sudo systemctl stop www.example.com.service

    $ systemctl status www.example.com.service
    www.example.com.service - Example Web Server
              Loaded: loaded (/etc/systemd/system/www.example.com.service; enabled)
              Active: inactive (dead) since Mon 2013-01-28 16:51:12 GMT; 1s ago
             Process: 10695 ExecStart=/usr/bin/twistd --nodaemon --pidfile= web --port 8080 --path . (code=exited, status=0/SUCCESS)

Socket Activation
-----------------
First you need to understand what "socket activation" is.
This extract from the `systemd daemon man page <http://www.freedesktop.org/software/systemd/man/daemon.html>`_ explains it quite clearly.

    In a socket-based activation scheme the creation and binding of the listening socket as primary communication channel of daemons to local (and sometimes remote) clients is moved out of the daemon code and into the init system.

    Based on per-daemon configuration the init system installs the sockets and then hands them off to the spawned process as soon as the respective daemon is to be started.

    Optionally activation of the service can be delayed until the first inbound traffic arrives at the socket, to implement on-demand activation of daemons.

    However, the primary advantage of this scheme is that all providers and all consumers of the sockets can be started in parallel as soon as all sockets are established.

    In addition to that daemons can be restarted with losing only a minimal number of client transactions or even any client request at all (the latter is particularly true for state-less protocols, such as DNS or syslog), because the socket stays bound and accessible during the restart, and all requests are queued while the daemon cannot process them.

Another benefit of socket activation is that ``systemd`` can listen on privileged ports and start Twisted with privileges already dropped. This allows a Twisted service to be configured and restarted by a non-root user.

Twisted (since version 12.2) includes a `systemd endpoint API and a corresponding string ports syntax <endpoints>`_ which allows a Twisted service to inherit a listening socket from ``systemd``\ .

The following example builds on the previous example, demonstrating how to enable socket activation for a simple Twisted web server.

.. note::

   Before continuing, stop the previous example service with the following command:

   .. code-block:: console

       $ sudo systemctl stop www.example.com.service

Create a systemd.socket file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create the `systemd.socket <http://www.freedesktop.org/software/systemd/man/systemd.socket.html>`_ file at ``/etc/systemd/system/www.example.com.socket`` with the following content:

:download:`/etc/systemd/system/www.example.com.socket <listings/systemd/www.example.com.socket>`

.. literalinclude:: listings/systemd/www.example.com.socket
   :language: ini

This configuration file contains the following important directives:

ListenStream=0.0.0.0:80

  This option configures ``systemd`` to create a listening TCP socket bound to all local IPv4 addresses on port 80.

WantedBy=sockets.target

  This is
  a `special target <http://www.freedesktop.org/software/systemd/man/systemd.special.html#sockets.target>`_ used by all socket activated services. ``systemd`` will automatically bind to all such socket activation ports during boot up.

You also need to modify the ``systemd.service`` file as follows:

:download:`/etc/systemd/system/www.example.com.service <listings/systemd/www.example.com.socketactivated.service>`

.. literalinclude:: listings/systemd/www.example.com.socketactivated.service
   :language: ini

Note the following important directives and changes:

ExecStart

  The ``domain=INET`` endpoint argument makes ``twistd`` treat the inherited file descriptor as an IPv4 socket.

  The ``index=0`` endpoint argument makes ``twistd`` adopt the first file descriptor inherited from ``systemd``\ .

  Socket activation is also technically possible with other socket families and types, but Twisted currently only accepts IPv4 and IPv6 TCP sockets. See :ref:`limitations` below.

NonBlocking

  This must be set to ``true`` to ensure that ``systemd`` passes non-blocking sockets to Twisted.

[Install]

  In this example, the ``[Install]`` section has been moved to the socket configuration file.

Reload ``systemd`` so that it reads the updated configuration files.

.. code-block:: console

    $ sudo systemctl daemon-reload

Start and enable the socket
~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can now start ``systemd`` listening on the socket with the following command:

.. code-block:: console

    $ sudo systemctl start www.example.com.socket

This command refers specifically to the socket configuration file, **not** the service file.

``systemd`` should now be listening on port 80

.. code-block:: console

    $ systemctl status www.example.com.socket
    www.example.com.socket
              Loaded: loaded (/etc/systemd/system/www.example.com.socket; disabled)
              Active: active (listening) since Tue 2013-01-29 14:53:17 GMT; 7s ago

    Jan 29 14:53:17 zorin.lan systemd[1]: Listening on www.example.com.socket.

But ``twistd`` should not yet have started.
You can verify this using the ``systemctl`` command. eg

.. code-block:: console

    $ systemctl status www.example.com.service
    www.example.com.service - Example Web Server
              Loaded: loaded (/etc/systemd/system/www.example.com.service; static)
              Active: inactive (dead) since Tue 2013-01-29 14:48:42 GMT; 6min ago

Enable the socket, so that it will be started automatically with the other socket activated services during boot up.

.. code-block:: console

    $ sudo systemctl enable www.example.com.socket
    ln -s '/etc/systemd/system/www.example.com.socket' '/etc/systemd/system/sockets.target.wants/www.example.com.socket'

Activate the port to start the service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Now try connecting to `http://localhost:80 <http://localhost:80>`_ in your web browser.

``systemd`` will accept the connection and start ``twistd``\ , passing it the listening socket.
You can verify this by using systemctl to report the status of the service. eg

.. code-block:: console

    $ systemctl status www.example.com.service
    www.example.com.service - Example Web Server
              Loaded: loaded (/etc/systemd/system/www.example.com.service; static)
              Active: active (running) since Tue 2013-01-29 15:02:20 GMT; 3s ago
            Main PID: 25605 (twistd)
              CGroup: name=systemd:/system/www.example.com.service
                      └─25605 /usr/bin/python /usr/bin/twistd --nodaemon --pidfile= web --port systemd:domain=INET:index=0 --path .

    Jan 29 15:02:20 zorin.lan systemd[1]: Started Example Web Server.
    Jan 29 15:02:20 zorin.lan twistd[25605]: 2013-01-29 15:02:20+0000 [-] Log opened.
    Jan 29 15:02:20 zorin.lan twistd[25605]: 2013-01-29 15:02:20+0000 [-] twistd 12.1.0 (/usr/bin/python 2.7.3) starting up.
    Jan 29 15:02:20 zorin.lan twistd[25605]: 2013-01-29 15:02:20+0000 [-] reactor class: twisted.internet.epollreactor.EPollReactor.
    Jan 29 15:02:20 zorin.lan twistd[25605]: 2013-01-29 15:02:20+0000 [-] Site starting on 80
    Jan 29 15:02:20 zorin.lan twistd[25605]: 2013-01-29 15:02:20+0000 [-] Starting factory <twisted.web.server.Site instance at 0x24be758>

Conclusion
----------
In this tutorial you have learned how to deploy a Twisted service using ``systemd``\ .
You have also learned how the service can be started on demand, using socket activation.

.. _limitations:

Limitations and Known Issues
----------------------------
#. Twisted can not accept UNIX or datagram sockets from ``systemd``\ .
#. Twisted does not support listening for SSL connections on sockets inherited from ``systemd``\ .

Further Reading
---------------
- `systemd Documentation <http://www.freedesktop.org/wiki/Software/systemd/>`_
