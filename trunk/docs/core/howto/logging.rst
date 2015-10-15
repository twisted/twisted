
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted's Legacy Logging System: ``twisted.python.log``
=======================================================


.. note::

    There is now a new logging system in Twisted (:doc:`you can read about how to use it here <logger>` and :api:`twisted.logger <its API reference here>`) which is a replacement for :api:`twisted.python.log <twisted.python.log>`.

    The old logging API, described here, remains for compatibility, and is now implemented as a client of the new logging system.

    New code should adopt the new API.

Basic usage
-----------
    
Twisted provides a simple and flexible logging system in the :api:`twisted.python.log <twisted.python.log>` module.  It has three commonly used
functions:
      
:api:`twisted.python.log.LogPublisher.msg <msg>` 
      
  Logs a new message.  For example:
  
  .. code-block:: python
  
      from twisted.python import log
      log.msg('Hello, world.')

:api:`twisted.python.log.err <err>` 
      
  Writes a failure to the log, including traceback information (if any).
  You can pass it a :api:`twisted.python.failure.Failure <Failure>` or Exception instance, or
  nothing.  If you pass something else, it will be converted to a string
  with ``repr`` and logged.
  
  If you pass nothing, it will construct a Failure from the
  currently active exception, which makes it convenient to use in an ``except`` clause:
  
  .. code-block:: python
  
      try:
          x = 1 / 0
      except:
          log.err()   # will log the ZeroDivisionError

:api:`twisted.python.log.startLogging <startLogging>` 
      
  Starts logging to a given file-like object.  For example:
  
  .. code-block:: python
      
      log.startLogging(open('/var/log/foo.log', 'w'))
  
  or:
  
  .. code-block:: python
      
      log.startLogging(sys.stdout)
  
  or:
  
  .. code-block:: python
      
      from twisted.python.logfile import DailyLogFile
      
      log.startLogging(DailyLogFile.fromFullPath("/var/log/foo.log"))
  
  By default, ``startLogging`` will also redirect anything written
  to ``sys.stdout`` and ``sys.stderr`` to the log.  You
  can disable this by passing ``setStdout=False`` to
  ``startLogging`` .

Before ``startLogging`` is called, log messages will be
discarded and errors will be written to stderr.


Logging and twistd
~~~~~~~~~~~~~~~~~~
    
If you are using ``twistd`` to run your daemon, it
will take care of calling ``startLogging`` for you, and will also
rotate log files.  See :ref:`twistd and tac <core-howto-application-twistd>` 
and the ``twistd`` man page for details of using
twistd.


Log files
~~~~~~~~~
    
The :api:`twisted.python.logfile <twisted.python.logfile>` module provides
some standard classes suitable for use with ``startLogging`` , such
as :api:`twisted.python.logfile.DailyLogFile <DailyLogFile>` ,
which will rotate the log to a new file once per day.


Using the standard library logging module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    
If your application uses the
Python `standard    library logging module <http://docs.python.org/library/logging.html>`_ or you want to use its easy configuration but
don't want to lose twisted-produced messages, the observer
:api:`twisted.python.log.PythonLoggingObserver <PythonLoggingObserver>` 
should be useful to you.

You just start it like any other observer:

.. code-block:: python
    
    observer = log.PythonLoggingObserver()
    observer.start()

Then `configure the    standard library logging module <http://docs.python.org/library/logging.html>`_ to behave as you want.

This method allows you to customize the log level received by the
standard library logging module using the ``logLevel`` keyword:

.. code-block:: python

    log.msg("This is important!", logLevel=logging.CRITICAL)
    log.msg("Don't mind", logLevel=logging.DEBUG)

Unless ``logLevel`` is provided, logging.INFO is used for ``log.msg`` 
and ``logging.ERROR`` is used for ``log.err`` .

One special care should be made when you use special configuration of
the standard library logging module: some handlers (e.g. SMTP, HTTP) use the network and
so can block inside the reactor loop. *Nothing* in ``PythonLoggingObserver`` is
done to prevent that.


Writing log observers
---------------------
    
Log observers are the basis of the Twisted logging system.
Whenever ``log.msg`` (or ``log.err`` ) is called, an
event is emitted.  The event is passed to each observer which has been
registered.  There can be any number of observers, and each can treat
the event in any way desired.
An example of
a log observer in Twisted is the ``emit`` method of :api:`twisted.python.log.FileLogObserver <FileLogObserver>` .
``FileLogObserver`` , used by
``startLogging`` , writes events to a log file.  A log observer
is just a callable that accepts a dictionary as its only argument.  You can
then register it to receive all log events (in addition to any other
observers):

.. code-block:: python
    
    twisted.python.log.addObserver(yourCallable)
    
The dictionary will have at least two items:
      
message
      
  The message (a list, usually of strings)
  for this log event, as passed to ``log.msg`` or the
  message in the failure passed to ``log.err`` .

isError
      
  This is a boolean that will be true if this event came from a call to
  ``log.err`` .  If this is set, there may be a ``failure`` 
  item in the dictionary as will, with a Failure object in it.

Other items the built in logging functionality may add include:
      
printed
      
  This message was captured from ``sys.stdout`` , i.e. this
  message came from a ``print`` statement.  If
  ``isError`` is also true, it came from
  ``sys.stderr`` .

You can pass additional items to the event dictionary by passing keyword
arguments to ``log.msg`` and ``log.err`` .  The standard
log observers will ignore dictionary items they don't use.

Important notes:

- Never block in a log observer, as it may run in main Twisted thread.
  This means you can't use socket or syslog standard library logging backends.
- The observer needs to be thread safe if you anticipate using threads
  in your program.


Customizing ``twistd``  logging
-------------------------------

The behavior of the logging that ``twistd`` does can be
customized either with the ``--logger`` option or by setting the
``ILogObserver`` component on the application object.  See the :doc:`Application document <application>` for more information.
