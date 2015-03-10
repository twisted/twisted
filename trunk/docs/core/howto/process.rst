
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using Processes
===============






Overview
--------



Along with connection to servers across the internet, Twisted also
connects to local processes with much the same API. The API is described in
more detail in the documentation of:

- :api:`twisted.internet.interfaces.IReactorProcess <twisted.internet.interfaces.IReactorProcess>` 
- :api:`twisted.internet.interfaces.IProcessTransport <twisted.internet.interfaces.IProcessTransport>` 
- :api:`twisted.internet.interfaces.IProcessProtocol <twisted.internet.interfaces.IProcessProtocol>` 




    



Running Another Process
-----------------------



Processes are run through the reactor,
using ``reactor.spawnProcess`` . Pipes are created to the child process,
and added to the reactor core so that the application will not block while
sending data into or pulling data out of the new
process. ``reactor.spawnProcess`` requires two arguments, 
``processProtocol`` and ``executable`` , and optionally takes
several more: ``args`` , ``environment`` , 
``path`` , ``userID`` , ``groupID`` , 
``usePTY`` , and ``childFDs`` . Not all of these are
available on Windows.






.. code-block:: python

    
    from twisted.internet import reactor
    
    processProtocol = MyProcessProtocol()
    reactor.spawnProcess(processProtocol, executable, args=[program, arg1, arg2],
                         env={'HOME': os.environ['HOME']}, path,
                         uid, gid, usePTY, childFDs)







- ``processProtocol`` should be an instance of a subclass of
  :api:`twisted.internet.protocol.ProcessProtocol <twisted.internet.protocol.ProcessProtocol>` . The
  interface is described below.
- ``executable`` is the full path of the program to run. It
  will be connected to processProtocol.
- ``args`` is a list of command line arguments to be passed to
  the process. ``args[0]`` should be the name of the process.
- ``env`` is a dictionary containing the environment to pass
  through to the process.
- ``path`` is the directory to run the process in. The child
  will switch to the given directory just before starting the new program.
  The default is to stay in the current directory.
- ``uid`` and ``gid`` are the user ID and group ID to
  run the subprocess as. Of course, changing identities will be more likely
  to succeed if you start as root.
- ``usePTY`` specifies whether the child process should be run
  with a pty, or if it should just get a pair of pipes.  Whether a program
  needs to be run with a PTY or not depends on the particulars of that
  program.  Often, programs which primarily interact with users via a terminal
  do need a PTY.
- ``childFDs`` lets you specify how the child's file
  descriptors should be set up. Each key is a file descriptor number (an
  integer) as seen by the child. 0, 1, and 2 are usually stdin, stdout, and
  stderr, but some programs may be instructed to use additional fds through
  command-line arguments or environment variables. Each value is either an
  integer specifying one of the parent's current file descriptors, the
  string "r" which creates a pipe that the parent can read from, or the
  string "w" which creates a pipe that the parent can write to. If
  ``childFDs`` is not provided, a default is used which creates the
  usual stdin-writer, stdout-reader, and stderr-reader pipes.





``args`` and ``env`` have empty default values, but
many programs depend upon them to be set correctly. At the very least, 
``args[0]`` should probably be the same as ``executable`` .
If you just provide ``os.environ`` for ``env`` , the child
program will inherit the environment from the current process, which is
usually the civilized thing to do (unless you want to explicitly clean the
environment as a security precaution). The default is to give an empty ``env`` to the child.




``reactor.spawnProcess`` returns an instance that implements :api:`twisted.internet.interfaces.IProcessTransport <IProcessTransport>`.


Writing a ProcessProtocol
-------------------------



The ProcessProtocol you pass to ``spawnProcess`` is your
interaction with the process. It has a very similar signature to a regular
Protocol, but it has several extra methods to deal with events specific to
a process. In our example, we will interface with 'wc' to create a word count
of user-given text. First, we'll start by importing the required modules, and
writing the initialization for our ProcessProtocol.





.. code-block:: python

    
    from twisted.internet import protocol
    class WCProcessProtocol(protocol.ProcessProtocol):
    
        def __init__(self, text):
            self.text = text




When the ProcessProtocol is connected to the protocol, it has the
connectionMade method called. In our protocol, we will write our text to the
standard input of our process and then close standard input, to let the
process know we are done writing to it.





.. code-block:: python

    
    ...
        def connectionMade(self):
            self.transport.write(self.text)
            self.transport.closeStdin()




At this point, the process has received the data, and it's time for us
to read the results. Instead of being received in ``dataReceived`` ,
data from standard output is received in ``outReceived`` . This is
to distinguish it from data on standard error.





.. code-block:: python

    
    ...
        def outReceived(self, data):
            fieldLength = len(data) / 3
            lines = int(data[:fieldLength])
            words = int(data[fieldLength:fieldLength*2])
            chars = int(data[fieldLength*2:])
            self.transport.loseConnection()
            self.receiveCounts(lines, words, chars)




Now, the process has parsed the output, and ended the connection to the
process. Then it sends the results on to the final method, receiveCounts.
This is for users of the class to override, so as to do other things with
the data. For our demonstration, we will just print the results.





.. code-block:: python

    
    ...
        def receiveCounts(self, lines, words, chars):
            print 'Received counts from wc.'
            print 'Lines:', lines
            print 'Words:', words
            print 'Characters:', chars




We're done! To use our WCProcessProtocol, we create an instance, and pass
it to spawnProcess.





.. code-block:: python

    
    from twisted.internet import reactor
    wcProcess = WCProcessProtocol("accessing protocols through Twisted is fun!\n")
    reactor.spawnProcess(wcProcess, 'wc', ['wc'])
    reactor.run()






Things that can happen to your ProcessProtocol
----------------------------------------------



These are the methods that you can usefully override in your subclass of 
``ProcessProtocol`` :







- ``.connectionMade()`` : This is called when the program is
  started, and makes a good place to write data into the stdin pipe (using
  ``self.transport.write`` ).
- ``.outReceived(data)`` : This is called with data that was
  received from the process' stdout pipe. Pipes tend to provide data in
  larger chunks than sockets (one kilobyte is a common buffer size), so you
  may not experience the "random dribs and drabs" behavior typical of
  network sockets, but regardless you should be prepared to deal if you
  don't get all your data in a single call. To do it properly,
  ``outReceived`` ought to simply accumulate the data and put off
  doing anything with it until the process has finished.
- ``.errReceived(data)`` : This is called with data from the
  process' stderr pipe. It behaves just like ``outReceived`` .
- ``.inConnectionLost`` : This is called when the reactor notices
  that the process' stdin pipe has closed. Programs don't typically close
  their own stdin, so this will probably get called when your
  ProcessProtocol has shut down the write side with ``self.transport.loseConnection`` .
- ``.outConnectionLost`` : This is called when the program closes
  its stdout pipe. This usually happens when the program terminates.
- ``.errConnectionLost`` : Same as
  ``outConnectionLost`` , but for stderr instead of stdout.
- ``.processExited(status)`` : This is called when the child
  process has been reaped, and receives information about the process' exit
  status. The status is passed in the form of a :api:`twisted.python.failure.Failure <Failure>` instance, created with a
  ``.value`` that either holds a :api:`twisted.internet.error.ProcessDone <ProcessDone>` object if the process
  terminated normally (it died of natural causes instead of receiving a
  signal, and if the exit code was 0), or a :api:`twisted.internet.error.ProcessTerminated <ProcessTerminated>` object (with an
  ``.exitCode`` attribute) if something went wrong.
- ``.processEnded(status)`` : This is called when all the file
  descriptors associated with the child process have been closed and the
  process has been reaped.  This means it is the last callback which will be
  made onto a ``ProcessProtocol`` .  The ``status`` parameter
  has the same meaning as it does for ``processExited`` .





The base-class definitions of most of these functions are no-ops. This will
result in all stdout and stderr being thrown away. Note that it is important
for data you don't care about to be thrown away: if the pipe were not read,
the child process would eventually block as it tried to write to a full
pipe.






Things you can do from your ProcessProtocol
-------------------------------------------



The following are the basic ways to control the child process:







- ``self.transport.write(data)`` : Stuff some data in the stdin
  pipe. Note that this ``write`` method will queue any data that can't
  be written immediately. Writing will resume in the future when the pipe
  becomes writable again.
- ``self.transport.closeStdin`` : Close the stdin pipe. Programs
  which act as filters (reading from stdin, modifying the data, writing to
  stdout) usually take this as a sign that they should finish their job and
  terminate. For these programs, it is important to close stdin when you're
  done with it, otherwise the child process will never quit.
- ``self.transport.closeStdout`` : Not usually called, since you're
  putting the process into a state where any attempt to write to stdout will
  cause a SIGPIPE error. This isn't a nice thing to do to the poor
  process.
- ``self.transport.closeStderr`` : Not usually called, same reason
  as ``closeStdout`` .
- ``self.transport.loseConnection`` : Close all three pipes.
- ``self.transport.signalProcess('KILL')`` : Kill the child
  process. This will eventually result in ``processEnded`` being
  called.







Verbose Example
---------------



Here is an example that is rather verbose about exactly when all the
methods are called. It writes a number of lines into the ``wc`` 
program and then parses the output.





:download:`process.py <listings/process/process.py>`

.. literalinclude:: listings/process/process.py


The exact output of this program depends upon the relative timing of some
un-synchronized events. In particular, the program may observe the child
process close its stderr pipe before or after it reads data from the stdout
pipe. One possible transcript would look like this:





.. code-block:: console

    
    % ./process.py
    connectionMade!
    inConnectionLost! stdin is closed! (we probably did it)
    errConnectionLost! The child closed their stderr.
    outReceived! with 24 bytes!
    outConnectionLost! The child closed their stdout!
    I saw 40 lines
    processEnded, status 0
    quitting
    Main loop terminated.
    %





Doing it the Easy Way
---------------------



Frequently, one just needs a simple way to get all the output from a
program. In the blocking world, you might use ``commands.getoutput`` from the standard library, but
using that in an event-driven program will cause everything else to stall
until the command finishes. (in addition, the SIGCHLD handler used by that
function does not play well with Twisted's own signal handling). For these
cases, the :api:`twisted.internet.utils.getProcessOutput <twisted.internet.utils.getProcessOutput>` 
function can be used. Here is a simple example:





:download:`quotes.py <listings/process/quotes.py>`

.. literalinclude:: listings/process/quotes.py


If you only need the final exit code (like ``commands.getstatusoutput(cmd)[0]`` ), the :api:`twisted.internet.utils.getProcessValue <twisted.internet.utils.getProcessValue>` function is
useful. Here is an example:





:download:`trueandfalse.py <listings/process/trueandfalse.py>`

.. literalinclude:: listings/process/trueandfalse.py



Mapping File Descriptors
------------------------



"stdin" , "stdout" , and "stderr" are just conventions.
Programs which operate as filters generally accept input on fd0, write their
output on fd1, and emit error messages on fd2. This is common enough that
the standard C library provides macros like "stdin" to mean fd0, and
shells interpret the pipe character "|" to mean "redirect fd1 from one command into fd0 of the next command" .




But these are just conventions, and programs are free to use additional
file descriptors or even ignore the standard three entirely. The"childFDs" argument allows you to specify exactly what kind of files
descriptors the child process should be given.




Each child FD can be put into one of three states:






- Mapped to a parent FD: this causes the child's reads and writes to
  come from or go to the same source/destination as the parent.
- Feeding into a pipe which can be read by the parent.
- Feeding from a pipe which the parent writes into.





Mapping the child FDs to the parent's is very commonly used to send the
child's stderr output to the same place as the parent's. When you run a
program from the shell, it will typically leave fds 0, 1, and 2 mapped to
the shell's 0, 1, and 2, allowing you to see the child program's output on
the same terminal you used to launch the child. Likewise, inetd will
typically map both stdin and stdout to the network socket, and may map
stderr to the same socket or to some kind of logging mechanism. This allows
the child program to be implemented with no knowledge of the network: it
merely speaks its protocol by doing reads on fd0 and writes on fd1.




Feeding into a parent's read pipe is used to gather output from the
child, and is by far the most common way of interacting with child
processes.




Feeding from a parent's write pipe allows the parent to control the
child. Programs like "bc" or "ftp" can be controlled this way, by
writing commands into their stdin stream.




The "childFDs" dictionary maps file descriptor numbers (as will be
seen by the child process) to one of these three states. To map the fd to
one of the parent's fds, simply provide the fd number as the value. To map
it to a read pipe, use the string "r" as the value. To map it to a
write pipe, use the string "w" .




For example, the default mapping sets up the standard stdin/stdout/stderr
pipes. It is implemented with the following dictionary:





.. code-block:: python

    
    childFDs = { 0: "w", 1: "r", 2: "r" }




To launch a process which reads and writes to the same places that the
parent python program does, use this:





.. code-block:: python

    
    childFDs = { 0: 0, 1: 1, 2: 2}




To write into an additional fd (say it is fd number 4), use this:





.. code-block:: python

    
    childFDs = { 0: "w", 1: "r", 2: "r" , 4: "w"}







ProcessProtocols with extra file descriptors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



When you provide a "childFDs" dictionary with more than the normal
three fds, you need additional methods to access those pipes. These methods
are more generalized than the ``.outReceived`` ones described above.
In fact, those methods (``outReceived`` and 
``errReceived`` ) are actually just wrappers left in for
compatibility with older code, written before this generalized fd mapping was
implemented. The new list of things that can happen to your ProcessProtocol
is as follows:







- ``.connectionMade`` : This is called when the program is
  started.
- ``.childDataReceived(childFD, data)`` : This is called with
  data that was received from one of the process' output pipes (i.e. where
  the childFDs value was "r" . The actual file number (from the point of
  view of the child process) is in "childFD" . For compatibility, the
  default implementation of ``.childDataReceived`` dispatches to
  ``.outReceived`` or ``.errReceived`` when "childFD" 
  is 1 or 2.
- ``.childConnectionLost(childFD)`` : This is called when the
  reactor notices that one of the process' pipes has been closed. This
  either means you have just closed down the parent's end of the pipe (with
  ``.transport.closeChildFD`` ), the child closed the pipe
  explicitly (sometimes to indicate EOF), or the child process has
  terminated and the kernel has closed all of its pipes. The "childFD" 
  argument tells you which pipe was closed. Note that you can only find out
  about file descriptors which were mapped to pipes: when they are mapped to
  existing fds the parent has no way to notice when they've been closed. For
  compatibility, the default implementation dispatches to
  ``.inConnectionLost`` , ``.outConnectionLost`` , or
  ``.errConnectionLost`` .
- ``.processEnded(status)`` : This is called when the child
  process has been reaped, and all pipes have been closed. This insures that
  all data written by the child prior to its death will be received before
  ``.processEnded`` is invoked.






In addition to those methods, there are other methods available to
influence the child process:







- ``self.transport.writeToChild(childFD, data)`` : Stuff some
  data into an input pipe. ``.write`` simply writes to
  childFD=0.
- ``self.transport.closeChildFD(childFD)`` : Close one of the
  child's pipes. Closing an input pipe is a common way to indicate EOF to
  the child process. Closing an output pipe is neither very friendly nor
  very useful.






Examples
~~~~~~~~



GnuPG, the encryption program, can use additional file descriptors to
accept a passphrase and emit status output. These are distinct from stdin
(used to accept the crypttext), stdout (used to emit the plaintext), and
stderr (used to emit human-readable status/warning messages). The passphrase
FD reads until the pipe is closed and uses the resulting string to unlock
the secret key that performs the actual decryption. The status FD emits
machine-parseable status messages to indicate the validity of the signature,
which key the message was encrypted to, etc.




gpg accepts command-line arguments to specify what these fds are, and
then assumes that they have been opened by the parent before the gpg process
is started. It simply performs reads and writes to these fd numbers.




To invoke gpg in decryption/verification mode, you would do something
like the following:





.. code-block:: python

    
    class GPGProtocol(ProcessProtocol):
        def __init__(self, crypttext):
            self.crypttext = crypttext
            self.plaintext = ""
            self.status = ""
        def connectionMade(self):
            self.transport.writeToChild(3, self.passphrase)
            self.transport.closeChildFD(3)
            self.transport.writeToChild(0, self.crypttext)
            self.transport.closeChildFD(0)
        def childDataReceived(self, childFD, data):
            if childFD == 1: self.plaintext += data
            if childFD == 4: self.status += data
        def processEnded(self, status):
            rc = status.value.exitCode
            if rc == 0:
                self.deferred.callback(self)
            else:
                self.deferred.errback(rc)
    
    def decrypt(crypttext):
        gp = GPGProtocol(crypttext)
        gp.deferred = Deferred()
        cmd = ["gpg", "--decrypt", "--passphrase-fd", "3", "--status-fd", "4",
               "--batch"]
        p = reactor.spawnProcess(gp, cmd[0], cmd, env=None,
                                 childFDs={0:"w", 1:"r", 2:2, 3:"w", 4:"r"})
        return gp.deferred




In this example, the status output could be parsed after the fact. It
could, of course, be parsed on the fly, as it is a simple line-oriented
protocol. Methods from LineReceiver could be mixed in to make this parsing
more convenient.




The stderr mapping ("2:2" ) used will cause any GPG errors to be
emitted by the parent program, just as if those errors had caused in the
parent itself. This is sometimes desirable (it roughly corresponds to
letting exceptions propagate upwards), especially if you do not expect to
encounter errors in the child process and want them to be more visible to
the end user. The alternative is to map stderr to a read-pipe and handle any
such output from within the ProcessProtocol (roughly corresponding to
catching the exception locally).

  

