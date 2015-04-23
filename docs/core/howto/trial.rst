
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Test-driven development with Twisted
====================================





Writing good code is hard, or at least it can be. A major challenge is
to ensure that your code remains correct as you add new functionality.




`Unit testing <http://en.wikipedia.org/wiki/Unit_test>`_ is a
modern, light-weight testing methodology in widespread use in many
programming languages. Development that relies on unit tests is often
referred to as Test-Driven Development
(`TDD <http://en.wikipedia.org/wiki/Test-driven_development>`_ ).
Most Twisted code is tested using TDD.




To gain a solid understanding of unit testing in Python, you should read
the `unittest --Unit testing framework chapter <http://docs.python.org/library/unittest.html>`_ of the `Python LibraryReference <http://docs.python.org/library/index.html>`_ . There is a lot of information available online and in
books.





Introductory example of Python unit testing
-------------------------------------------



This document is principally a guide to Trial, Twisted's unit testing
framework. Trial is based on Python's unit testing framework. While we do not
aim to give a comprehensive guide to general Python unit testing, it will be
helpful to consider a simple non-networked example before expanding to cover
networking code that requires the special capabilities of Trial. If you are
already familiar with unit test in Python, jump straight to the section
specific to :ref:`testing Twisted code <core-howto-trial-twisted>` .




.. note::
   In what follows we will make a series of refinements
   to some simple classes. In order to keep the examples and source code links
   complete and to allow you to run Trial on the intermediate results at every
   stage, I add ``_N``  (where the ``N``  are successive
   integers) to file names to keep them separate. This is a minor visual
   distraction that should be ignored.







Creating an API and writing tests
---------------------------------



We'll create a library for arithmetic calculation. First, create a
project structure with a directory called ``calculus`` containing an empty ``__init__.py`` file.




Then put the following simple class definition API into ``calculus/base_1.py`` :





:download:`base_1.py <listings/trial/calculus/base_1.py>`

.. literalinclude:: listings/trial/calculus/base_1.py


(Ignore the ``test-case-name`` comment for
now. You'll see why that's useful :ref:`below <core-howto-trial-comment>` .)




We've written the interface, but not the code. Now we'll write a set of
tests. At this point of development, we'll be expecting all tests to
fail. Don't worry, that's part of the point. Once we have a test framework
functioning, and we have some decent tests written (and failing!), we'll go
and do the actual development of our calculation API. This is the preferred
way to work for many people using TDD - write tests first, make sure they
fail, then do development. Others are not so strict and write tests after
doing the development.




Create a ``test`` directory beneath ``calculus`` , with an empty ``__init__.py`` file. In a ``calculus/test/test_base_1.py`` , put the
following:





:download:`test_base_1.py <listings/trial/calculus/test/test_base_1.py>`

.. literalinclude:: listings/trial/calculus/test/test_base_1.py


You should now have the following 4 files:


.. code-block:: console

    
    calculus/__init__.py
    calculus/base_1.py
    calculus/test/__init__.py
    calculus/test/test_base_1.py






To run the tests, there are two things you must set up. Make sure
you get both done - nothing below will work unless you do.




First, make sure that the directory that *contains* your
``calculus`` directory is in your Python load path. If you're
using the Bash shell on some form of unix (e.g., Linux, Mac OS X), run
``PYTHONPATH="$PYTHONPATH:`pwd`/.."`` at
the command line in the ``calculus`` directory. Once you have your
Python path set up correctly, you should be able to run Python from the
command line and ``import calculus`` without seeing
an import error.




Second, make sure you can run the ``trial`` 
command. That is, make sure the directory containing the ``trial`` 
program on you system is in your shell's ``PATH`` . The easiest way to check if you have this is to
try running ``trial --help`` at the command line. If
you see a list of invocation options, you're in business. If your shell
reports something like ``trial: command not found`` ,
make sure you have Twisted installed properly, and that the Twisted
``bin`` directory is in your ``PATH`` . If
you don't know how to do this, get some local help, or figure it out by
searching online for information on setting and changing environment
variables for you operating system.




With those (one-time) preliminary steps out of the way, let's perform
the tests. Run ``trial calculus.test.test_base_1`` from the
command line when you are in the directory containing the ``calculus`` 
directory.

You should see the following output (though your files are probably not in
``/tmp`` ):





.. code-block:: console

    
    $ trial calculus.test.test_base_1
    calculus.test.test_base_1
      CalculationTestCase
        test_add ...                                                         [FAIL]
        test_divide ...                                                      [FAIL]
        test_multiply ...                                                    [FAIL]
        test_subtract ...                                                    [FAIL]
    
    ===============================================================================
    [FAIL]
    Traceback (most recent call last):
      File "/tmp/calculus/test/test_base_1.py", line 8, in test_add
        self.assertEqual(result, 11)
    twisted.trial.unittest.FailTest: not equal:
    a = None
    b = 11
    
    
    calculus.test.test_base_1.CalculationTestCase.test_add
    ===============================================================================
    [FAIL]
    Traceback (most recent call last):
      File "/tmp/calculus/test/test_base_1.py", line 23, in test_divide
        self.assertEqual(result, 2)
    twisted.trial.unittest.FailTest: not equal:
    a = None
    b = 2
    
    
    calculus.test.test_base_1.CalculationTestCase.test_divide
    ===============================================================================
    [FAIL]
    Traceback (most recent call last):
      File "/tmp/calculus/test/test_base_1.py", line 18, in test_multiply
        self.assertEqual(result, 60)
    twisted.trial.unittest.FailTest: not equal:
    a = None
    b = 60
    
    
    calculus.test.test_base_1.CalculationTestCase.test_multiply
    ===============================================================================
    [FAIL]
    Traceback (most recent call last):
      File "/tmp/calculus/test/test_base_1.py", line 13, in test_subtract
        self.assertEqual(result, 4)
    twisted.trial.unittest.FailTest: not equal:
    a = None
    b = 4
    
    
    calculus.test.test_base_1.CalculationTestCase.test_subtract
    -------------------------------------------------------------------------------
    Ran 4 tests in 0.042s
    
    FAILED (failures=4)




How to interpret this output? You get a list of the individual tests, each
followed by its result. By default, failures are printed at the end, but this
can be changed with the ``-e`` (or ``--rterrors`` ) option.




One very useful thing in this output is the fully-qualified name of the
failed tests. This appears at the bottom of each =-delimited area of the
output. This allows you to copy and paste it to just run a single test you're
interested in. In our example, you could run ``trial calculus.test.test_base_1.CalculationTestCase.test_subtract`` from the
shell.




Note that trial can use different reporters to modify its output. Run
``trial --help-reporters`` to see a list of
reporters.





The tests can be run by ``trial`` in multiple ways:


- ``trial calculus`` : run all the tests for the
  calculus package.
- ``trial calculus.test`` : run using Python's
  ``import`` notation.
- ``trial calculus.test.test_base_1`` : as above, for
  a specific test module. You can follow that logic by putting your class name
  and even a method name to only run those specific tests.
- .. _core-howto-trial-comment:
  
  
  
  
  
  ``trial --testmodule=calculus/base_1.py`` : use the ``test-case-name`` comment in the first line of
  ``calculus/base_1.py`` to find the tests.
- ``trial calculus/test`` : run all the tests in the
  test directory (not recommended).
- ``trial calculus/test/test_base_1.py`` : run a
  specific test file (not recommended).


The first 3 versions using full qualified names are strongly encouraged: they
are much more reliable and they allow you to easily be more selective in your
test runs.






You'll notice that Trial creates a ``_trial_temp`` directory in
the directory where you run the tests. This has a file called
``test.log`` which contains the log output of the tests (created
using ``log.msg`` or ``log.err`` functions). Examine this file if you add
logging to your tests.





Making the tests pass
---------------------



Now that we have a working test framework in place, and our tests are
failing (as expected) we can go and try to implement the correct API. We'll do
that in a new version of the above base_1
module, ``calculus/base_2.py`` :





:download:`base_2.py <listings/trial/calculus/base_2.py>`

.. literalinclude:: listings/trial/calculus/base_2.py


We'll also create a new version of test_base_1 which imports and tests this
new implementation,
in ``calculus/test_base_2.py`` :






:download:`test_base_2.py <listings/trial/calculus/test/test_base_2.py>`

.. literalinclude:: listings/trial/calculus/test/test_base_2.py

is a copy of test_base_1, but with the import changed. Run ``trial`` again as above, and your tests should now pass:





.. code-block:: console

    
    $ trial calculus.test.test_base_2
    
    Running 4 tests.
    calculus.test.test_base
      CalculationTestCase
        test_add ...                                                           [OK]
        test_divide ...                                                        [OK]
        test_multiply ...                                                      [OK]
        test_subtract ...                                                      [OK]
    
    -------------------------------------------------------------------------------
    Ran 4 tests in 0.067s
    
    PASSED (successes=4)





Factoring out common test logic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



You'll notice that our test file contains redundant code. Let's get rid
of that. Python's unit testing framework allows your test class to define a
``setUp`` method that is called before
*each* test method in the class. This allows you to add attributes
to ``self`` that can be used in test
methods. We'll also add a parameterized test method to further simplify the
code.




Note that a test class may also provide the counterpart of ``setUp`` , named ``tearDown`` ,
which will be called after *each* test (whether successful or
not). ``tearDown`` is mainly used for post-test
cleanup purposes. We will not use ``tearDown`` 
until later.




Create ``calculus/test/test_base_2b.py`` as
follows:





:download:`test_base_2b.py <listings/trial/calculus/test/test_base_2b.py>`

.. literalinclude:: listings/trial/calculus/test/test_base_2b.py


Much cleaner, isn't it?




We'll now add some additional error tests. Testing just for successful
use of the API is generally not enough, especially if you expect your code
to be used by others. Let's make sure the ``Calculation`` class raises exceptions if someone tries
to call its methods with arguments that cannot be converted to
integers.




We arrive at ``calculus/test/test_base_3.py`` :





:download:`test_base_3.py <listings/trial/calculus/test/test_base_3.py>`

.. literalinclude:: listings/trial/calculus/test/test_base_3.py


We've added four new tests and one general-purpose function, ``_test_error`` . This function uses the ``assertRaises`` method, which takes an exception class,
a function to run and its arguments, and checks that calling the function
on the arguments does indeed raise the given exception.




If you run the above, you'll see that not all tests fail. In Python it's
often valid to add and multiply objects of different and even differing
types, so the code in the add and multiply tests does not raise an exception
and those tests therefore fail. So let's add explicit type conversion to
our API class. This brings us to ``calculus/base_3.py`` :





:download:`base_3.py <listings/trial/calculus/base_3.py>`

.. literalinclude:: listings/trial/calculus/base_3.py


Here the ``_make_ints`` helper function tries to
convert a list into a list of equivalent integers, and raises a ``TypeError`` in case the conversion goes wrong.

.. note::

   The ``int`` conversion can also raise a ``TypeError`` if passed something of
   the wrong type, such as a list. We'll just let that exception go by, as
   ``TypeError`` is already what we want in case something goes wrong.

.. _core-howto-trial-twisted:








Twisted specific testing
------------------------



Up to this point we've been doing fairly standard Python unit testing.
With only a few cosmetic changes (most importantly, directly importing
``unittest`` instead of using Twisted's :api:`twisted.trial.unittest <unittest>` version) we could make the
above tests run using Python's standard library unit testing framework.




Here we will assume a basic familiarity with Twisted's network I/O, timing,
and Deferred APIs.  If you haven't already read them, you should read the
documentation on :doc:`Writing Servers <servers>` , :doc:`Writing Clients <clients>` ,
and :doc:`Deferreds <defer>` .




Now we'll get to the real point of this tutorial and take advantage of
Trial to test Twisted code.





Testing a protocol
------------------



We'll now create a custom protocol to invoke our class from a
telnet-like session. We'll remotely call commands with arguments and read back
the response. The goal will be to test our network code without creating
sockets.





Creating and testing the server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



First we'll write the tests, and then explain what they do.  The first
version of the remote test code is:





:download:`test_remote_1.py <listings/trial/calculus/test/test_remote_1.py>`

.. literalinclude:: listings/trial/calculus/test/test_remote_1.py


To fully understand this client, it helps a lot to be comfortable with
the Factory/Protocol/Transport pattern used in Twisted.




We first create a protocol factory object. Note that we have yet to see
the ``RemoteCalculationFactory`` class. It is in
``calculus/remote_1.py`` below. We
call ``buildProtocol`` to ask the factory to build us a
protocol object that knows how to talk to our server.  We then make a fake
network transport, an instance of ``twisted.test.proto_helpers.StringTransport`` 
class (note that test packages are generally not part of Twisted's public API;``twisted.test.proto_helpers`` is an exception).  This fake
transport is the key to the communications. It is used to emulate a network
connection without a network. The address and port passed to ``buildProtocol`` 
are typically used by the factory to choose to immediately deny remote connections; since we're using a fake transport, we can choose any value that will be acceptable to the factory. In this case the factory just ignores the address, so we don't need to pick anything in particular.




Testing protocols without the use of real network connections is both simple and recommended when testing Twisted
code.  Even though there are many tests in Twisted that use the network,
most good tests don't. The problem with unit tests and networking is that
networks aren't reliable. We cannot know that they will exhibit reasonable
behavior all the time. This creates intermittent test failures due to
network vagaries. Right now we're trying to test our Twisted code, not
network reliability.  By setting up and using a fake transport, we can
write 100% reliable tests. We can also test network failures in a deterministic manner, another important part of your complete test suite.




The final key to understanding this client code is the ``_test`` method. The call to ``dataReceived`` simulates data arriving on the network
transport. But where does it arrive? It's handed to the ``lineReceived`` method of the protocol instance (in
``calculus/remote_1.py`` below). So the client
is essentially tricking the server into thinking it has received the
operation and the arguments over the network. The server (once again, see
below) hands over the work to its ``CalculationProxy`` object which in turn hands it to its
``Calculation`` instance. The result is written
back via ``sendLine`` (into the fake string
transport object), and is then immediately available to the client, who
fetches it with ``tr.value()`` and checks that it
has the expected value. So there's quite a lot going on behind the scenes
in the two-line ``_test`` method above.




*Finally* , let's see the implementation of this protocol. Put the
following into ``calculus/remote_1.py`` :





:download:`remote_1.py <listings/trial/calculus/remote_1.py>`

.. literalinclude:: listings/trial/calculus/remote_1.py


As mentioned, this server creates a protocol that inherits from :api:`twisted.protocols.basic.LineReceiver <basic.LineReceiver>` , and then a
factory that uses it as protocol. The only trick is the ``CalculationProxy`` object, which calls ``Calculation`` methods through ``remote_*`` methods. This pattern is used frequently in
Twisted, because it is very explicit about what methods you are making
accessible.




If you run this test (``trial calculus.test.test_remote_1`` ), everything should be fine. You can also
run a server to test it with a telnet client. To do that, call ``python calculus/remote_1.py`` . You should have the following output:





.. code-block:: console

    
    2008-04-25 10:53:27+0200 [-] Log opened.
    2008-04-25 10:53:27+0200 [-] __main__.RemoteCalculationFactory starting on 46194
    2008-04-25 10:53:27+0200 [-] Starting factory <__main__.RemoteCalculationFactory instance at 0x846a0cc>




46194 is replaced by a random port. You can then call telnet on it:




::

    
    $ telnet localhost 46194
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    add 4123 9423
    13546




It works!





Creating and testing the client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Of course, what we build is not particularly useful for now: we'll now build
a client for our server, to be able to use it inside a Python program. And it
will serve our next purpose.




Create ``calculus/test/test_client_1.py`` :





:download:`test_client_1.py <listings/trial/calculus/test/test_client_1.py>`

.. literalinclude:: listings/trial/calculus/test/test_client_1.py


It's really symmetric to the server test cases. The only tricky part is
that we don't use a client factory. We're lazy, and it's not very useful in
the client part, so we instantiate the protocol directly.




Incidentally, we have introduced a very important concept here: the tests
now return a Deferred object, and the assertion is done in a callback. When
a test returns a Deferred, the reactor is run until the Deferred fires and
its callbacks run.  The
important thing to do here is to **not forget to return the Deferred** . If you do, your tests will pass even if nothing is asserted.
That's also why it's important to make tests fail first: if your tests pass
whereas you know they shouldn't, there is a problem in your tests.




We'll now add the remote client class to produce ``calculus/client_1.py`` :





:download:`client_1.py <listings/trial/calculus/client_1.py>`

.. literalinclude:: listings/trial/calculus/client_1.py



More good practices
-------------------




Testing scheduling
~~~~~~~~~~~~~~~~~~



When testing code that involves the passage of time, waiting e.g. for a two hour timeout to occur in a test is not very realistic. Twisted provides a solution to this, the :api:`twisted.internet.task.Clock <Clock>` class that allows one to simulate the passage of time.




As an example we'll test the code for client request timeout: since our client
uses TCP it can hang for a long time (firewall, connectivity problems, etc...).
So generally we need to implement timeouts on the client side. Basically it's
just that we send a request, don't receive a response and expect a timeout error
to be triggered after a certain duration.





:download:`test_client_2.py <listings/trial/calculus/test/test_client_2.py>`

.. literalinclude:: listings/trial/calculus/test/test_client_2.py


What happens here? We instantiate our protocol as usual, the only trick
is to create the clock, and assign ``proto.callLater`` to
``clock.callLater`` . Thus, every ``callLater`` 
call in the protocol will finish before ``clock.advance()`` returns.




In the new test (test_timeout), we call ``clock.advance`` , that simulates an advance in time
(logically it's similar to a ``time.sleep`` call). And
we just have to verify that our Deferred got a timeout error.




Let's implement that in our code.





:download:`client_2.py <listings/trial/calculus/client_2.py>`

.. literalinclude:: listings/trial/calculus/client_2.py



If everything completed successfully,
it is important to remember to cancel the
``DelayedCall`` 
returned by ``callLater`` .





Cleaning up after tests
~~~~~~~~~~~~~~~~~~~~~~~



This chapter is mainly intended for people who want to have sockets or
processes created in their tests. If it's still not obvious, you must try to
avoid using them, because it ends up with a lot of problems, one of
them being intermittent failures. And intermittent failures are the plague
of automated tests.




To actually test that, we'll launch a server with our protocol.





:download:`test_remote_2.py <listings/trial/calculus/test/test_remote_2.py>`

.. literalinclude:: listings/trial/calculus/test/test_remote_2.py


Recent versions of trial will fail loudly if you remove the
``stopListening`` call, which is good.




Also, you should be aware that ``tearDown`` will
be called in any case, after success or failure. So don't expect every
object you created in the test method to be present, because your tests may
have failed in the middle.




Trial also has a ``addCleanup`` method, which makes
these kind of cleanups easy and removes the need for ``tearDown`` . For example, you could remove the code in ``_test`` 
this way:





.. code-block:: python

    
    def setUp(self):
        factory = RemoteCalculationFactory()
        self.port = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.addCleanup(self.port.stopListening)
    
    def _test(self, op, a, b, expected):
        creator = protocol.ClientCreator(reactor, RemoteCalculationClient)
        def cb(client):
            self.addCleanup(self.client.transport.loseConnection)
            return getattr(client, op)(a, b).addCallback(self.assertEqual, expected)
        return creator.connectTCP('127.0.0.1', self.port.getHost().port).addCallback(cb)




This removes the need of a ``tearDown`` method, and you don't have to check for
the value of self.client: you only call addCleanup when the client is
created.





Handling logged errors
~~~~~~~~~~~~~~~~~~~~~~



Currently, if you send an invalid command or invalid arguments to our
server, it logs an exception and closes the connection. This is a perfectly
valid behavior, but for the sake of this tutorial, we want to return an error
to the user if they send invalid operators, and log any errors on server side.
So we'll want a test like this:





.. code-block:: python

    
    def test_invalidParameters(self):
        self.proto.dataReceived('add foo bar\r\n')
        self.assertEqual(self.tr.value(), "error\r\n")





:download:`remote_2.py <listings/trial/calculus/remote_2.py>`

.. literalinclude:: listings/trial/calculus/remote_2.py


If you try something like that, it will not work. Here is the output you should have:





.. code-block:: console

    
    trial calculus.test.test_remote_3.RemoteCalculationTestCase.test_invalidParameters
    calculus.test.test_remote_3
      RemoteCalculationTestCase
        test_invalidParameters ...                                          [ERROR]
    
    ===============================================================================
    [ERROR]: calculus.test.test_remote_3.RemoteCalculationTestCase.test_invalidParameters
    
    Traceback (most recent call last):
      File "/tmp/calculus/remote_2.py", line 27, in lineReceived
        result = op(a, b)
      File "/tmp/calculus/base_3.py", line 11, in add
        a, b = self._make_ints(a, b)
      File "/tmp/calculus/base_3.py", line 8, in _make_ints
        raise TypeError
    exceptions.TypeError:
    -------------------------------------------------------------------------------
    Ran 1 tests in 0.004s
    
    FAILED (errors=1)




At first, you could think there is a problem, because you catch this
exception. But in fact trial doesn't let you do that without controlling it:
you must expect logged errors and clean them. To do that, you have to use the
``flushLoggedErrors`` method. You call it with the
exception you expect, and it returns the list of exceptions logged since the
start of the test. Generally, you'll want to check that this list has the
expected length, or possibly that each exception has an expected message. We do
the former in our test:





:download:`test_remote_3.py <listings/trial/calculus/test/test_remote_3.py>`

.. literalinclude:: listings/trial/calculus/test/test_remote_3.py



Resolve a bug
-------------



A bug was left over during the development of the timeout (probably several
bugs, but that's not the point), concerning the reuse of the protocol when you
got a timeout: the connection is not dropped, so you can get timeout forever.
Generally a user will come to you saying "I have this strange problem on
my crappy network. It seems you could solve it with doing XXX at
YYY."




Actually, this bug can be corrected several ways. But if you correct it
without adding tests, one day you'll face a big problem: regression.
So the first step is adding a failing test.





:download:`test_client_3.py <listings/trial/calculus/test/test_client_3.py>`

.. literalinclude:: listings/trial/calculus/test/test_client_3.py


What have we done here ?


- We switched to StringTransportWithDisconnection. This transport manages
  ``loseConnection`` and forwards it to its protocol.
- We assign the protocol to the transport via the ``protocol`` attribute.
- We check that after a timeout our connection has closed.







For doing that, we then use the ``TimeoutMixin`` 
class, that does almost everything we want. The great thing is that it almost
changes nothing to our class.





:download:`client_3.py <listings/trial/calculus/client_3.py>`

.. literalinclude:: listings/trial/calculus/client_3.py



Testing Deferreds without the reactor
-------------------------------------



Above we learned about returning Deferreds from test methods in order to make
assertions about their results, or side-effects that only happen after they
fire.  This can be useful, but we don't actually need the feature in this
example.  Because we were careful to use ``Clock`` , we
don't need the global reactor to run in our tests.  Instead of returning the
Deferred with a callback attached to it which performs the necessary assertions,
we can use a testing helper,
:api:`twisted.trial.unittest.SynchronousTestCase.successResultOf <successResultOf>` (and
the corresponding error-case helper
:api:`twisted.trial.unittest.SynchronousTestCase.failureResultOf <failureResultOf>` ), to
extract its result and make assertions against it directly.  Compared to
returning a Deferred, this avoids the problem of forgetting to return the
Deferred, improves the stack trace reported when the assertion fails, and avoids
the complexity of using global reactor (which, for example, may then require
cleanup).





:download:`test_client_4.py <listings/trial/calculus/test/test_client_4.py>`

.. literalinclude:: listings/trial/calculus/test/test_client_4.py


This version of the code makes the same assertions, but no longer returns any
Deferreds from any test methods.  Instead of making assertions about the result
of the Deferred in a callback, it makes the assertions as soon as
it *knows* the Deferred is supposed to have a result (in
the ``_test`` method and in ``test_timeout`` 
and ``test_timeoutConnectionLost`` ).  The possibility
of *knowing* exactly when a Deferred is supposed to have a test is what
makes ``successResultOf`` useful in unit testing, but prevents it from being
applicable to non-testing purposes.




``successResultOf`` will raise an exception (failing the test) if
the ``Deferred`` passed to it does not have a result, or has a failure
result.  Similarly, ``failureResultOf`` will raise an exception (also
failing the test) if the ``Deferred`` passed to it does not have a
result, or has a success result.  There is a third helper method for testing the
final case,
:api:`twisted.trial.unittest.SynchronousTestCase.assertNoResult <assertNoResult>` ,
which only raises an exception (failing the test) if the ``Deferred`` passed
to it *has* a result (either success or failure).





Dropping into a debugger
------------------------



In the course of writing and running your tests, it is often helpful to
employ the use of a debugger. This can be particularly helpful in tracking down
where the source of a troublesome bug is in your code. Python's standard library
includes a debugger in the form of the `pdb <http://docs.python.org/library/pdb.html>`_ module.
Running your tests with ``pdb`` is as simple as invoking
twisted with the ``--debug`` option, which will start ``pdb`` at the beginning of the execution of your test
suite.




Trial also provides a ``--debugger`` option which can
run your test suite using another debugger instead. To specify a debugger other
than ``pdb`` , pass in the fully-qualified name of an
object that provides the same interface as ``pdb`` .
Most third-party debuggers tend to implement an interface similar to ``pdb`` , or at least provide a wrapper object that
does. For example, invoking trial with the line ``trial --debug --debugger pudb`` will open the `PuDB <http://pypi.python.org/pypi/pudb>`_ debugger instead, provided
it is properly installed.





Code coverage
-------------



Code coverage is one of the aspects of software testing that shows how much
your tests cross (cover) the code of your program. There are different kinds of
measures: path coverage, condition coverage, statement coverage... We'll only
consider statement coverage here, whether a line has been executed or not.




Trial has an option to generate the statement coverage of your tests.
This option is --coverage. It creates a coverage directory in _trial_temp,
with a file .cover for every module used during the tests. The ones
interesting for us are calculus.base.cover and calculus.remote.cover. Each line
starts with a counter showing how many times the line was executed during the
tests, or the marker '>>>>>>' if the line was not
covered. If you went through the whole tutorial to this point, you should
have complete coverage :).




Again, this is only another useful pointer, but it doesn't mean your
code is perfect: your tests should consider every possible input and
output, to get **full** coverage (condition, path, etc.) as well
.





Conclusion
----------



So what did you learn in this document?


- How to use the trial command-line tool to run your tests
- How to use string transports to test individual clients and servers
  without creating sockets
- If you really want to create sockets, how to cleanly do it so that it
  doesn't have bad side effects
- And some small tips you can't live without.

If one of the topics still looks cloudy to you, please give us your feedback!
You can file tickets to improve this document - learn how to contribute `on the Twisted web site <http://twistedmatrix.com/trac/wiki/TwistedDevelopment/>`_.
