
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Writing tests for Twisted code using Trial
==========================================






Trial basics
------------



**Trial** is Twisted's testing framework.  It provides a
library for writing test cases and utility functions for working with the
Twisted environment in your tests, and a command-line utility for running your
tests. Trial is built on the Python standard library's ``unittest`` 
module. For more information on how Trial finds tests, see the
:api:`twisted.trial.runner.TestLoader.loadModule <loadModule>` documentation.




To run all the Twisted tests, do:





.. code-block:: console

    
    $ trial twisted




Refer to the Trial man page for other command-line options.





Trial directories
-----------------



You might notice a new ``_trial_temp`` folder in the
current working directory after Trial completes the tests. This folder is the
working directory for the Trial process. It can be used by unit tests and 
allows them to write whatever data they like to disk, and not worry
about polluting the current working directory.




Folders named ``_trial_temp-<counter>`` are
created if two instances of Trial are run in parallel from the same directory,
so as to avoid giving two different test-runs the same temporary directory.




The :api:`twisted.python.lockfile <twisted.python.lockfile>` utility is used to lock
the ``_trial_temp`` directories. On Linux, this results
in symlinks to pids. On Windows, directories are created with a single file with
a pid as the contents. These lock files will be cleaned up if Trial exits normally
and otherwise they will be left behind. They should be cleaned up the next time
Trial tries to use the directory they lock, but it's also safe to delete them
manually if desired.





Twisted-specific quirks: reactor, Deferreds, callLater
------------------------------------------------------



The standard Python ``unittest`` framework, from which Trial is
derived, is ideal for testing code with a fairly linear flow of control.
Twisted is an asynchronous networking framework which provides a clean,
sensible way to establish functions that are run in response to events (like
timers and incoming data), which creates a highly non-linear flow of control.
Trial has a few extensions which help to test this kind of code. This section
provides some hints on how to use these extensions and how to best structure
your tests.





Leave the Reactor as you found it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Trial runs the entire test suite (over four thousand tests) in a single
process, with a single reactor. Therefore it is important that your test
leave the reactor in the same state as it found it. Leftover timers may
expire during somebody else's unsuspecting test. Leftover connection attempts
may complete (and fail) during a later test. These lead to intermittent
failures that wander from test to test and are very time-consuming to track
down.




If your test leaves event sources in the reactor, Trial will fail the test.
The ``tearDown`` method is a good place to put cleanup code: it is
always run regardless of whether your test passes or fails (like a ``finally`` 
clause in a try-except-finally construct). Exceptions in ``tearDown`` 
are flagged as errors and flunk the test. 
:api:`twisted.trial.unittest.TestCase.addCleanup <TestCase.addCleanup>` is
another useful tool for cleaning up.  With it, you can register callables to
clean up resources as the test allocates them.  Generally, code should be
written so that only resources allocated in the tests need to be cleaned up in
the tests.  Resources which are allocated internally by the implementation
should be cleaned up by the implementation.




If your code uses Deferreds or depends on the reactor running, you can
return a Deferred from your test method, setUp, or tearDown and Trial will
do the right thing. That is, it will run the reactor for you until the
Deferred has triggered and its callbacks have been run. Don't use 
``reactor.run()`` , ``reactor.stop()`` , ``reactor.crash()`` or ``reactor.iterate()`` in your tests.




Calls to ``reactor.callLater`` create :api:`twisted.internet.interfaces.IDelayedCall <IDelayedCall>` s.  These need to be run
or cancelled during a test, otherwise they will outlive the test.  This would
be bad, because they could interfere with a later test, causing confusing
failures in unrelated tests!  For this reason, Trial checks the reactor to make
sure there are no leftover :api:`twisted.internet.interfaces.IDelayedCall <IDelayedCall>` s in the reactor after a
test, and will fail the test if there are.  The cleanest and simplest way to
make sure this all works is to return a Deferred from your test.




Similarly, sockets created during a test should be closed by the end of the
test.  This applies to both listening ports and client connections.  So, calls
to ``reactor.listenTCP`` (and ``listenUNIX`` , and so on)
return :api:`twisted.internet.interfaces.IListeningPort <IListeningPort>` s, and these should be
cleaned up before a test ends by calling their :api:`twisted.internet.interfaces.IListeningPort.stopListening <stopListening>` method.
Calls to ``reactor.connectTCP`` return :api:`twisted.internet.interfaces.IConnector <IConnector>` s, which should be cleaned
up by calling their :api:`twisted.internet.interfaces.IConnector.disconnect <disconnect>` method.  Trial
will warn about unclosed sockets.




The golden rule is: If your tests call a function which returns a Deferred,
your test should return a Deferred.





Using Timers to Detect Failing Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



It is common for tests to establish some kind of fail-safe timeout that
will terminate the test in case something unexpected has happened and none of
the normal test-failure paths are followed. This timeout puts an upper bound
on the time that a test can consume, and prevents the entire test suite from
stalling because of a single test. This is especially important for the
Twisted test suite, because it is run automatically by the buildbot whenever
changes are committed to the Subversion repository.




The way to do this in Trial is to set the ``.timeout`` attribute
on your unit test method.  Set the attribute to the number of seconds you wish
to elapse before the test raises a timeout error.  Trial has a default timeout
which will be applied even if the ``timeout`` attribute is not set.
The Trial default timeout is usually sufficient and should be overridden only
in unusual cases.





Interacting with warnings in tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Trial includes specific support for interacting with Python's 
``warnings`` module.  This support allows warning-emitting code to
be written test-driven, just as any other code would be.  It also improves
the way in which warnings reporting when a test suite is running.




:api:`twisted.trial.unittest.TestCase.flushWarnings <TestCase.flushWarnings>` 
allows tests to be written which make assertions about what warnings have
been emitted during a particular test method. In order to test a warning with 
``flushWarnings`` , write a test which first invokes the code which
will emit a warning and then calls ``flushWarnings`` and makes
assertions about the result.  For example:





.. code-block:: python

    
    class SomeWarningsTests(TestCase):
        def test_warning(self):
            warnings.warn("foo is bad")
            self.assertEqual(len(self.flushWarnings()), 1)




Warnings emitted in tests which are not flushed will be included by the
default reporter in its output after the result of the test.  If Python's
warnings filter system (see `the-W command option to Python <http://docs.python.org/using/cmdline.html#cmdoption-unittest-discover-W>`_ ) is configured to treat a warning as an error,
then unflushed warnings will causes tests to fail and will be included in
the summary section of the default reporter.  Note that unlike usual
operation, when ``warnings.warn`` is called as part of a test
method, it will not raise an exception when warnings have been configured as
errors.  However, if called outside of a test method (for example, at module
scope in a test module or a module imported by a test module) then it 
*will* raise an exception.





Parallel test
~~~~~~~~~~~~~



In many situations, your unit tests may run faster if they are allowed to
run in parallel, such that blocking I/O calls allow other tests to continue.
Trial, like unittest, supports the -j parameter.  Run ``trial -j 3`` 
to run 3 test runners at the same time.




This requires care in your test creation.  Obviously, you need to ensure that
your code is otherwise content to work in a parallel fashion while working within
Twisted... and if you are using weird global variables in places, parallel tests
might reveal this.




However, if you have a test that fires up a schema on an external database
in the ``setUp`` function, does some operations on it in the test, and
then deletes that schema in the tearDown function, your tests will behave in an
unpredictable fashion as they tromp upon each other if they have their own
schema.  And this won't actually indicate a real error in your code, merely a
testing-specific race-condition.

  

