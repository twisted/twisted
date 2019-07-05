Ticket numbers in this file can be looked up by visiting
http://twistedmatrix.com/trac/ticket/<number>

.. towncrier release notes start

Twisted 19.2.0 (2019-04-07)
===========================

This is the final release that will support Python 3.4.

Features
--------

- twisted.internet.ssl.CertificateOptions now uses 32 random bytes instead of an MD5 hash for the ssl session identifier context. (#9463)
- DeferredLock and DeferredSemaphore can be used as asynchronous context
  managers on Python 3.5+. (#9546)
- t.i.b.BaseConnector has custom __repr__ (#9548)
- twisted.internet.ssl.optionsForClientTLS now supports validating IP addresses from the certificate subjectAltName (#9585)
- Twisted's minimum Cryptography requirement is now 2.5. (#9592)


Bugfixes
--------

- twisted.web.proxy.ReverseProxyResource fixed documentation and example snippet (#9192)
- twisted.python.failure.Failure.getTracebackObject now returns traceback objects whose frames can be passed into traceback.print_stack for better debugging of where the exception came from. (#9305)
- twisted.internet.ssl.KeyPair.generate: No longer generate 1024-bit RSA keys by default. Anyone who generated a key with this method using the default value should move to replace it immediately. (#9453)
- The message of twisted.internet.error.ConnectionAborted is no longer truncated. (#9522)
- twisted.enterprise.adbapi.ConnectionPool.connect now logs only the dbapiName and not the connection arguments, which may contain credentials (#9544)
- twisted.python.runtime.Platform.supportsINotify no longer considers the result of isDocker for its own result. (#9579)


Improved Documentation
----------------------

- The documentation for the the twisted.internet.interfaces.IConsumer, IProducer, and IPullProducer interfaces is more detailed. (#2546)
- The errback example in the docstring of twisted.logger.Logger.failure has been corrected. (#9334)
- The sample code in the "Twisted Web In 60 Seconds" tutorial runs on Python 3. (#9559)


Misc
----

- #8921, #9071, #9125, #9428, #9536, #9540, #9580


Conch
-----

Features
~~~~~~~~

- twisted.conch.ssh.keys can now read private keys in the new "openssh-key-v1" format, introduced in OpenSSH 6.5 and made the default in OpenSSH 7.8. (#9515)


Bugfixes
~~~~~~~~

- Conch now uses pyca/cryptography for Diffie-Hellman key generation and agreement. (#8831)


Misc
~~~~

- #9584


Web
---

Features
~~~~~~~~

- twisted.web.client.HostnameCachingHTTPSPolicy was added as a new contextFactory option.  The policy caches a specified number of twisted.internet.interfaces.IOpenSSLClientConnectionCreator instances to to avoid the cost of instantiating a connection creator for multiple requests to the same host. (#9138)


Bugfixes
~~~~~~~~

- twisted.web.http.Request.cookies, twisted.web.http.HTTPChannel.writeHeaders, and twisted.web.http_headers.Headers were all vulnerable to header injection attacks.  They now replace linear whitespace ('\r', '\n', and '\r\n') with a single space.  twisted.web.http.Reqeuest.cookies also replaces semicolons (';') with a single space. (#9420)
- twisted.web.client.Request and twisted.web.client.HTTPClient were both vulnerable to header injection attacks.  They now replace linear whitespace ('\r', '\n', and '\r\n') with a single space. (#9421)


Mail
----

No significant changes.


Words
-----

No significant changes.


Names
-----

Features
~~~~~~~~

- twisted.names.dns now has IRecord implementations for the SSHFP and TSIG record types. (#9373)


Twisted 18.9.0 (2018-10-10)
===========================

Features
--------

- twisted.internet._sslverify.ClientTLSOptions no longer raises IDNAError when given an IPv6 address as a hostname in a HTTPS URL. (#9433)
- The repr() of a twisted.internet.base.DelayedCall now encodes the same information as its str(), exposing details of its scheduling and target callable. (#9481)
- Python 3.7 is now supported. (#9502)


Bugfixes
--------

- twisted.logger.LogBeginner's default critical observer now prints tracebacks for new and legacy log system events through the use of the new eventAsText API.  This API also does not raise an error for non-ascii encoded data in Python2, it attempts as well as possible to format the traceback. (#7927)
- Syntax error under Python 3.7 fixed for twisted.conch.manhole and
  twisted.main.imap4. (#9384)
- `trial -j` reports tracebacks on test failures under Python 3. (#9436)
- Properly format multi-byte and non-ascii encoded data in a traceback. (#9456)
- twisted.python.rebuild now functions on Python 3.7. (#9492)
- HTTP/2 server connections will no longer time out active downloads that take too long. (#9529)


Improved Documentation
----------------------

- Several minor formatting problems in the API documentation have been corrected. (#9461)
- The documentation of twisted.internet.defer.Deferred.fromFuture() has been updated to reflect upstream changes. (#9539)


Deprecations and Removals
-------------------------

- async keyword argument is deprecated in twisted.conch.manhole
  (ManholeInterpreter.write and Manhole.add) and in
  twisted.main.imap4.IMAP4Server.sendUntaggedResponse,
  isAsync keyword argument is introduced instead. (#9384)


Misc
----

- #9379, #9485, #9489, #9499, #9501, #9511, #9514, #9523, #9524, #9525, #9538


Conch
-----

Bugfixes
~~~~~~~~

- twisted.conch.keys.Key.public returns the same twisted.conch.keys.Key instance when it is already a public key instead of failing with an exception. (#9441)
- RSA private keys are no longer corrupted during loading, allowing OpenSSL's fast-path to operate for RSA signing. (#9518)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- The documentation for IConchUser.gotGlobalRequest() is more accurate. (#9413)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.conch.ssh.filetransfer.ClientDirectory's use as an iterator has been deprecated. (#9527)


Web
---

Bugfixes
~~~~~~~~

- twisted.web.server.Request.getSession now returns a new session if the
  previous session has expired. (#9288)


Misc
~~~~

- #9479, #9480, #9482, #9491


Mail
----

No significant changes.


Words
-----

No significant changes.


Names
-----

No significant changes.


Twisted 18.7.0 (2018-07-10)
===========================

Features
--------

- Cancelling a Deferred returned by twisted.internet.defer.inlineCallbacks now cancels the Deferred it is waiting on. (#4632)
- twisted.application.internet.ClientService now accepts a function to initialize or validate a connection before it is returned by the whenConnected method as the prepareConnection argument. (#8375)
- Traceback generated for twisted.internet.defer.inlineCallbacks now includes the full stack of inlineCallbacks generators between catcher and raiser (before it only contained raiser's stack). (#9176)
- Add optional cwd argument to twisted.runner.procmon.ProcMon.addProcess (#9287)
- twisted.python.failure.Failure tracebacks generated by coroutines scheduled with twisted.internet.defer.ensureDeferred - i.e. any Deferred-awaiting coroutine - now contain fewer extraneous frames from the trampoline implementation, and correctly indicate the source of exceptions raised in other call stacks - i.e. the function that raised the exception.  In other words: if you 'await' a function that raises an exception, you'll be able to see where the error came from. (#9459)


Bugfixes
--------

- On UNIX-like platforms, Twisted attempts to recover from EMFILE when accepting connections on TCP and UNIX ports by shedding incoming clients. (#5368)
- The documentation of IReactorTime.getDelayedCalls() has been corrected to indicate that the method returns a list, not a tuple. (#9418)
- "python -m twisted web --help" now refers to "--listen" instead of the non-existing "--http" (#9434)
- twisted.python.htmlizer.TokenPrinter now explicitly works on bytestrings. (#9442)
- twisted.enterprise.adbapi.ConnectionPool.runWithConnection and runInteraction now use the reactor that is passed to ConnectionPool's constructor. (#9467)


Improved Documentation
----------------------

- The Twisted Coding Standard now contains examples of how to mark up a feature as added in the next Twisted release. (#9460)


Deprecations and Removals
-------------------------

- Deprecate direct introspection of ProcMon's processes: processes should not be directly accessed or pickled. (#9287)
- twisted.internet.address.IPv4Address._bwHack and twisted.internet.address.UNIXAddress._bwHack, as well as the parameters to the constructors, deprecated since Twisted 11.0, have been removed. (#9450)


Misc
----

- #7495, #9399, #9406, #9411, #9425, #9439, #9449, #9450, #9452


Conch
-----

Features
~~~~~~~~

- twisted.conch.ssh.transport.SSHTransportBase now includes Twisted's version in the software version string it sends to the server, allowing servers to apply compatibility workarounds for bugs in particular client versions. (#9424)


Bugfixes
~~~~~~~~

- If the command run by twisted.conch.endpoints.SSHCommandClientEndpoint exits because of a delivered signal, the client protocol's connectionLost is now called with a ProcessTerminated exception instead of a ConnectionDone exception. (#9412)
- twisted.conch.ssh.transport.SSHTransportBase now correctly handles MSG_DEBUG with a false alwaysDisplay field on Python 2 (broken since 8.0.0). (#9422)
- twisted.conch.manhole.lastColorizedLine now does not throw a UnicodeDecodeError on non-ASCII input. (#9442)


Web
---

Features
~~~~~~~~

- Added support for SameSite cookies in ``http.Request.addCookie``. (#9387)


Bugfixes
~~~~~~~~

- twisted.web.server.GzipEncoderFactory would sometimes fail to gzip requests if the Accept-Encoding header contained whitespace between the comma-separated acceptable encodings. It now trims whitespace before checking if gzip is an acceptable encoding. (#9086)
- twisted.web.static.File renders directory listings on Python 2, including those with text paths. (#9438)
- twisted.python.http.Request now correcly parses multipart bodies on Python 3.7. (#9448)
- twisted.web.http.combinedLogFormatter (used by t.w.http.Server and t.w.server.Site) no longer produces DeprecationWarning about Request.getClientIP. (#9470)


Misc
~~~~

- #9432, #9466, #9479, #9480


Mail
----

No significant changes.


Words
-----

No significant changes.


Names
-----

Misc
~~~~

- #9398


Twisted 18.4.0 (2018-04-13)
===========================

Features
--------

- The --port/--https arguments to web plugin are now deprecated, in favor of
  --listen. The --listen argument can be given multiple times to listen on
  multiple ports. (#6670)
- Twisted now requires zope.interface 4.4.2 or higher across all platforms and
  Python versions. (#8149)
- The osx_platform setuptools extra has been renamed to macos_platform, with
  the former name being a compatibility alias. (#8848)
- Zsh completions are now provided for the twist command. (#9338)
- twisted.internet.endpoints.HostnameEndpoint now has a __repr__ method which
  includes the host and port to which the endpoint connects. (#9341)


Bugfixes
--------

- twistd now uses the UID's default GID to initialize groups when --uid is
  given but --gid is not. This prevents an unhandled TypeError from being
  raised when os.initgroups() is called. (#4442)
- twisted.protocols.basic.LineReceiver checks received lines' lengths against
  its MAX_LENGTH only after receiving a complete delimiter. A line ending in a
  multi-byte delimiter like '\r\n' might be split by the network, with the
  first part arriving before the rest; previously, LineReceiver erroneously
  disconnected if the first part, e.g. 'zzzz....\r' exceeded MAX_LENGTH.
  LineReceiver now checks received data against MAX_LENGTH plus the delimiter's
  length, allowing short reads to complete a line. (#6556)
- twisted.protocols.basic.LineOnlyReceiver disconnects the transport after
  receiving a line that exceeds MAX_LENGTH, like LineReceiver. (#6557)
- twisted.web.http.Request.getClientIP now returns the host part of the
  client's address when connected over IPv6. (#7704)
- twisted.application.service.IService is now documented as requiring the
  'running', 'name' and 'parent' attributes (the documentation previously
  implied they were required, but was unclear). (#7922)
- twisted.web.wsgi.WSGIResource no longer raises an exception when a client
  connects over IPv6. (#8241)
- When using TLS enable automatic ECDH curve selection on OpenSSL 1.0.2+
  instead of only supporting P-256 (#9210)
- twisted.trial._dist.worker and twisted.trial._dist.workertrial consistently
  pass bytes, not unicode to AMP. This fixes "trial -j" on Python 3. (#9264)
- twisted.trial.runner now uses the 'importlib' module instead of the 'imp'
  module on Python 3+. This eliminates DeprecationWarnings caused by importing
  'imp' on Python 3. (#9275)
- twisted.web.client.HTTP11ClientProtocol now closes the connection when the
  server is sending a header line which is longer than he line limit of
  twisted.protocols.basic.LineReceiver.MAX_LENGTH. (#9295)
- twisted.python.failure now handles long stacktraces better; in particular it
  will log tracebacks for stack overflow errors. (#9301)
- The "--_shell-completion" argument to twistd now works on Python 3. (#9303)
- twisted.python.failure.Failure now raises the wrapped exception in Python3,
  and self (Failure) n Python2 when trap() is called without a matching
  exception (#9307)
- Writing large amounts of data no longer implies repeated, expensive copying
  under Python 3. Python 3's write speeds are now as fast as Python 2's.
  (#9324)
- twisted.protocols.postfix now properly encodes errors which are unicode
  strings to bytes. (#9335)
- twisted.protocols.policies.ProtocolWrapper and
  twisted.protocols.tls.TLSMemoryBIOProtocol no longer create circular
  references that keep protocol instances in memory after connection is closed.
  (#9374)
- twisted.conch.ssh.transport.SSHTransportBase no longer strips trailing spaces
  from the SSH version string of the connected peer. (#9377)
- `trial -j` no longer crashes on Python 2 on test failure messages containing
  non-ASCII bytes. (#9378)
- RSA keys replaced with 2048bit ones in twisted.conch.test.keydata in order to
  be compatible with OpenSSH 7.6. (#9388)
- AsyncioSelectorReactor uses the global policy's event loop. asyncio libraries
  that retrieve the running event loop with get_event_loop() will now receive
  the one used by AsyncioSelectorReactor. (#9390)


Improved Documentation
----------------------

- public attributes of `twisted.logger.Logger` are now documented as
  attributes. (#8157)
- List indentation formatting errors have been corrected throughout the
  documentation. (#9256)


Deprecations and Removals
-------------------------

- twisted.protocols.basic.LineOnlyReceiver.lineLengthExceeded no longer returns
  twisted.internet.error.ConnectionLost. It instead directly disconnects the
  transport and returns None. (#6557)
- twisted.python.win32.getProgramsMenuPath and
  twisted.python.win32.getProgramFilesPath were deprecated in Twisted 15.3.0
  and have now been removed. (#9312)
- Python 3.3 is no longer supported. (#9352)


Misc
----

- #7033, #8887, #9204, #9289, #9291, #9292, #9293, #9302, #9336, #9355, #9356,
  #9364, #9375, #9381, #9382, #9389, #9391, #9393, #9394, #9396


Conch
-----

Bugfixes
~~~~~~~~

- twisted.plugins.cred_unix now properly converts a username and password from
  bytes to str on Python 3. In addition, passwords which are encrypted with
  SHA512 and SH256 are properly verified. This fixes running a conch server
  with: "twistd -n conch -d /etc/ssh/ --auth=unix". (#9130)
- In twisted.conch.scripts.conch, on Python 3 do not write bytes directly to
  sys.stderr. On Python 3, this fixes remote SSH execution of a command which
  fails. (#9344)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.conch.ssh.filetransfer.FileTransferClient.wasAFile attribute has been
  removed as it serves no purpose. (#9362)
- Removed deprecated support for PyCrypto key objects in conch (#9368)


Web
---

Features
~~~~~~~~

- The new twisted.iweb.IRequest.getClientAddress returns the IAddress provider
  representing the client's address. Callers should check the type of the
  returned value before using it. (#7707)
- Eliminate use of twisted.python.log in twisted.web modules. (#9280)


Bugfixes
~~~~~~~~

- Scripts ending with .rpy, .epy, and .cgi now execute properly in Twisted Web
  on Python 3. (#9271)
- twisted.web.http.Request and twisted.web.server.Request are once again
  hashable on Python 2, fixing a regression introduced in Twisted 17.5.0.
  (#9314)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- Correct reactor docstrings for twisted.web.client.Agent and
  twisted.web.client._StandardEndpointFactory to communicate interface
  requirements since 17.1. (#9274)
- The examples for the "Twisted Web in 60 Seconds" tutorial have been fixed to
  work on Python 3. (#9285)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.iweb.IRequest.getClientIP is deprecated. Use
  twisted.iweb.IRequest.getClientAddress instead (see #7707). (#7705)
- twisted.web.iweb.IRequest.getClient and its implementations (deprecated in
  #2552) have been removed. (#9395)


Mail
----

Bugfixes
~~~~~~~~

- twistd.mail.scripts.mailmail has been ported to Python 3. (#8487)
- twisted.mail.bounce now works on Python 3. (#9260)
- twisted.mail.pop3 and twisted.mail.pop3client now work on Python 3. (#9269)
- SMTP authentication in twisted.mail.smtp now works better on Python 3, due to
  improved improved bytes vs unicode handling. (#9299)


Misc
~~~~

- #9310


Words
-----

No significant changes.


Names
-----

No significant changes.


Twisted 17.9.0 (2017-09-23)
===========================

This is the last Twisted release where Python 3.3 is supported, on any
platform.

Features
--------

- twisted.python.failure.Failure is now a new-style class which subclasses
  BaseException. (#5519)
- twisted.internet.posixbase.PosixReactorBase.adoptStreamPort and
  twisted.internet.posixbase.PosixReactorBase.adoptStreamConnection now support
  AF_UNIX SOCK_STREAM sockets. (#5573)
-  (#8940)
- t.protocol.policies.TimeoutMixin.setTimeout and
  t.protocol.policies.TimeoutProtocol.cancelTimeout (used in
  t.protocol.policies.TimeoutFactory) no longer raise a
  t.internet.error.AlreadyCancelled exception when calling them for an already
  cancelled timeout. (#9131)
- twisted.web.template.flatten now supports coroutines that yield Deferreds.
  (#9199)
- twisted.web.client.HTTPConnectionPool passes the repr() of the endpoint to
  the client protocol factory, and the protocol factory adds that to its own
  repr(). This makes logs more useful. (#9235)
- Python 3.6 is now supported (#9240)


Bugfixes
--------

- twisted.python.logfile.BaseLogFile and subclasses now always open the file in
  binary mode, and will process text as UTF-8. (#6938)
- The `ssl:` endpoint now accepts `certKey` PEM files without trailing
  newlines. (#7530)
- Logger.__init__ sets the namespace to "<unknown>" instead of raising KeyError
  when unable to determine the namespace from the calling context. (#7930)
- twisted.internet._win32serialport updated to support pySerial 3.x and dropped
  pySerial 2.x support. (#8159)
- twisted.python.rebuild now works on Python 3. (#8213)
- twisted.web.server.Request.notifyFinish will now once again promptly notify
  applications of client disconnection (assuming that the client doesn't send a
  large amount of pipelined request data) rather than waiting for the timeout;
  this fixes a bug introduced in Twisted 16.3.0. (#8692)
- twisted.web.guard.HTTPAuthSessionWrapper configured with
  DigestCredentialFactory now works on both Python 2 and 3. (#9127)
- Detect when we’re being run using “-m twisted” or “-m twisted.trial” and use
  it to build an accurate usage message. (#9133)
- twisted.protocols.tls.TLSMemoryBIOProtocol now allows unregisterProducer to
  be called when no producer is registered, bringing it in line with other
  transports. (#9156)
- twisted.web web servers no longer print tracebacks when they timeout clients
  that do not respond to TLS CLOSE_NOTIFY messages. (#9157)
- twisted.mail.imap4 now works on Python 3. (#9161)
- twisted.python.shortcut now works on Python 3 in Windows. (#9170)
- Fix traceback forwarding with inlineCallbacks on python 3. (#9175)
- twisted.mail.imap4.MessageSet now treats * as larger than every message ID,
  leading to more consistent and robust behavior. (#9177)
- The following plugins can now be used on Python 3 with twistd: dns, inetd,
  portforward, procmon, socks, and words. (#9184)
- twisted.internet._win32serialport now uses serial.serialutil.to_bytes() to
  provide bytes in Python 3. (#9186)
- twisted.internet.reactor.spawnProcess() now does not fail on Python 3 in
  Windows if passed a bytes-encoded path argument. (#9200)
- twisted.protocols.ident now works on Python 3. (#9221)
- Ignore PyPy's implementation differences in base object class. (#9225)
- twisted.python.test.test_setup now passes with setuptools 36.2.1 (#9231)
- twisted.internet._win32serialport SerialPort._clearCommError() no longer
  raises AttributeError (#9252)
- twisted.trial.unittest.SynchronousTestCase and
  twisted.trial.unittest.TestCase now always run their tearDown methods, even
  when a test method fails with an exception. They also flush all errors logged
  by a test method before running another, ensuring the logged errors are
  associated with their originating test method. (#9267)


Improved Documentation
----------------------

- Trial's documentation now directly mentions the preferred way of running
  Trial, via "python -m twisted.trial". (#9052)
- twisted.internet.endpoints.HostnameEndpoint and
  twisted.internet.endpoints.TCP4Client endpoint documentation updated to
  correctly reflect that the timeout argument takes a float as well as an int.
  (#9151)
- Badges at top of README now correctly render as links to respective result
  pages on GitHub. (#9216)
- The example code for the trial tutorial is now compatible with Python3 and
  the current version of Twisted. (#9223)


Deprecations and Removals
-------------------------

- twisted.protocols.dict is deprecated. (#9141)
- gpsfix.py has been removed from the examples. It uses twisted.protocols.gps
  which was removed in Twisted 16.5.0. (#9253)
- oscardemo.py, which illustrates the use of twisted.words.protocols.oscar, as
  been removed. twisted.words.protocols.oscar was removed in Twisted 17.5.0.
  (#9255)


Misc
----

- #5949, #8566, #8650, #8944, #9159, #9160, #9162, #9196, #9219, #9228, #9229,
  #9230, #9247, #9248, #9249, #9251, #9254, #9262, #9276, #9308


Conch
-----

Bugfixes
~~~~~~~~

- twisted.conch.ssh.userauth.SSHUserAuthServer now gracefully handles
  unsupported authentication key types. (#9139)
- twisted.conch.client.default verifyHostKey now opens /dev/tty with no buffer
  to be compatible with Python 3. This lets the conch cli work with Python 3.
  (#9265)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.conch.ssh._cryptography_backports has been removed in favor of using
  int_to_bytes() and int_from_bytes() from cryptography.utils. (#9263)


Misc
~~~~

- #9158, #9272


Web
---

Features
~~~~~~~~

- twisted.web.static.File.contentTypes is now documented. (#5739)
- twisted.web.server.Request and any Twisted web server using it now support
  automatic fast responses to HTTP/1.1 and HTTP/2 OPTIONS * requests, and
  reject any other verb using the * URL form. (#9190)
- --add-header "HeaderName: Value" can be passed to twist web in order to set
  extra headers on all responses (#9241)


Bugfixes
~~~~~~~~

- twisted.web.client.HTTPClientFactory(...).gotHeaders(...) now handles a wrong
  Set-Cookie header without a traceback. (#9136)
- twisted.python.web.http.HTTPFactory now always opens logFile in binary mode
  and writes access logs in UTF-8, to avoid encoding issues and newline
  differences on Windows. (#9143)
- The code examples in "Using the Twisted Web Client" now work on Python 3.
  (#9172)
- twisted.web.server.Request and all web servers that use it now no longer send
  a default Content-Type header on responses that do not have a body (i.e. that
  set Content-Length: 0 or that send a 204 status code). (#9191)
- twisted.web.http.Request and all subclasses now correctly fire Deferreds
  returned from notifyFinish with errbacks when errors are encountered in
  HTTP/2 streams. (#9208)
- twisted.web.microdom, twisted.web.domhelpers, and twisted.web.sux now work on
  Python 3. (#9222)


Mail
----

Bugfixes
~~~~~~~~

- Sending a list of recipients with twisted.smtp.SenderFactory has been fixed.
  This fixes a problem found when running buildbot. (#9180)
- twisted.mail.imap4.IMAP4Server parses empty string literals even when they
  are the last argument to a command, such as LOGIN. (#9207)


Words
-----

Bugfixes
~~~~~~~~

- twisted.words.tap has been ported to Python 3 (#9169)


Misc
~~~~

- #9246


Names
-----

Bugfixes
~~~~~~~~

- Queries for unknown record types no longer incorrectly result in a server
  error. (#9095)
- Failed TCP connections for AFXR queries no longer raise an AttributeError.
  (#9174)


Twisted 17.5.0 (2017-06-04)
===========================

Bugfixes
--------

- spawnProcess no longer opens an unwanted console on Windows (#5726)
- The transition to the hyperlink package adds IPv6 support to
  twisted.python.url.URL. This is now deprecated and new code should use
  hyperlink directly (see #9126). (#8069)
- twisted.logger now buffers only 200 events by default (reduced from 65536)
  while waiting for observers to be configured. (#8164)
- The transition of twisted.python.url to using the hyperlink package enables a
  URL.click() with no arguments (or 0-length string argument) to resolve dot
  segments in the path. (#8184)
- twisted.protocols.finger now works on Python 3. (#8230)
- TLS-related tests now pass when run with OpenSSL 1.1.0. This makes tests pass
  again on macOS and Windows, as cryptography 1.8 and later include OpenSSL
  1.1.0. (#8898)
- UNIX socket endpoints now process all messages from recvmsg's ancillary data
  via twisted.internet.unix.Server.doRead/twisted.internet.unix.Client.doRead,
  while discarding and logging ones that don't contain file descriptors.
  (#8912)
- twisted.internet.endpoints.HostnameEndpoint and twisted.web.client.Agent work
  again with reactors that do not provide IReactorPluggableNameResolver. This
  undoes the changes that broke downstream users such as treq.testing. Note
  that passing reactors that do not provide IReactorPluggableNameResolver to
  either is deprecated. (#9032)
- A Python 3 Perspective Broker server which receives a remote call with
  keyword arguments from a Python 2 client will now decode any keys which are
  binary to strings instead of crashing. This fixes interoperability between
  Python 2 Buildbot clients and Python 3 Buildbot servers. (#9047)
- twisted.internet._threadedselect now works on both Python 2 and 3. (#9053)
- twisted.internet.interfaces.IResolverSimple implementers will now always be
  passed bytes, properly IDNA encoded if required, on Python 2. On Python 3,
  they will now be passed correctly IDNA-encoded Unicode forms of the domain,
  taking advantage of the idna library from PyPI if possible. This is to avoid
  Python's standard library (which has an out of date idna module) from mis-
  encoding domain names when non-ASCII Unicode is passed to it. (#9137)


Improved Documentation
----------------------

- The examples in Twisted howto "Using the Twisted Application Framework",
  section "Customizing twistd logging" have been updated to use latest logging
  modules and syntax (#9084)


Features
--------

- twisted.internet.defer.Deferred.asFuture and
  twisted.internet.defer.Deferred.fromFuture were added, allowing for easy
  transitions between asyncio coroutines (which await Futures) and twisted
  coroutines (which await Deferreds). (#8748)
- twisted.application.internet.ClientService.whenConnected now accepts an
  argument "failAfterFailures". If you set this to 1, the Deferred returned by
  whenConnected will errback when the connection attempt fails, rather than
  retrying forever. This lets you react (probably by stopping the
  ClientService) to connection errors that are likely to be persistent, such as
  using the wrong hostname, or not being connected to the internet at all.
  (#9116)
- twisted.protocols.tls.TLSMemoryBIOProtocol and anything that uses it
  indirectly including the TLS client and server endpoints now enables TLS 1.3
  cipher suites. (#9128)


Misc
----

- #8133, #8995, #8997, #9003, #9015, #9021, #9026, #9027, #9049, #9057, #9062,
  #9065, #9069, #9070, #9072, #9074, #9075, #9111, #9117, #9140, #9144, #9145


Deprecations and Removals
-------------------------

- twisted.runner.inetdconf.InvalidRPCServicesConfError,
  twisted.runner.inetdconf.RPCServicesConf, twisted.runner.inetdtap.RPCServer,
  and twisted.runner.portmap, deprecated since 16.2.0, have been removed.
  (#8464)
- twisted.python.url and twisted.python._url were modified to rely on
  hyperlink, a new package based on the Twisted URL implementation. Hyperlink
  adds support for IPv6 (fixing #8069), correct username/password encoding,
  better scheme/netloc inference, improved URL.click() behavior (fixing #8184),
  and more. For full docs see hyperlink.readthedocs.io and the CHANGELOG in the
  hyperlink GitHub repo. (#9126)


Conch
-----

Bugfixes
~~~~~~~~

- History-aware terminal protocols like twisted.conch.manhole.Manhole no longer
  raise a TypeError when a user visits a partial line they added to the command
  line history by pressing up arrow before return. (#9031)
- The telnet_echo.tac example had conflicting port callouts between runtime and
  documentation. File was altered to run on documented port, 6023. (#9055)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Remove diffie-hellman-group1-sha1 from twisted.conch. See https://weakdh.org/
  (#9019)
- Removed small and obscure elliptic curves from conch. The only curves conch
  supports now are the ones also supported by OpenSSH. (#9088)


Mail
----

Bugfixes
~~~~~~~~

- twisted.mail.smtp has been ported to Python 3. (#8770)


Names
-----

Bugfixes
~~~~~~~~

- RRHeader now converts its ttl argument to an integer, raising a TypeError if
  it cannot. (#8340)


Web
---

Bugfixes
~~~~~~~~

- twisted.web.cgi now works on Python 3 (#8009)
- twisted.web.distrib now works on Python 3 (#8010)
- twisted.web.http.HTTPFactory now propagates its reactor's callLater method to
  the HTTPChannel object, rather than having callLater grab the global reactor.
  This prevents the possibility of HTTPFactory logging using one reactor, but
  HTTPChannel running timeouts on another. (#8904)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- twisted.web.template.flattenString docstring now correctly references
  io.BytesIO (rather than NativeStringIO). (#9028)


Features
~~~~~~~~

- twisted.web.client now exposes the RequestGenerationFailed exception type.
  (#5310)
- twisted.web.client.Agent will now parse responses that begin with a status
  line that is missing a phrase. (#7673)
- twisted.web.http.HTTPChannel and twisted.web._http2.H2Connection have been
  enhanced so that after they time out they wait a small amount of time to
  allow the connection to close gracefully and, if it does not, they forcibly
  close it to avoid allowing malicious clients to forcibly keep the connection
  open. (#8902)


Misc
~~~~

- #8981, #9018, #9067, #9090, #9092, #9093, #9096


Words
-----

Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- twisted.words.protocols.oscar, which is client code for Oscar/ICQ, was
  deprecated in 16.2.0 and has now been removed. (#9024)


Twisted Core 17.1.0 (2017-02-04)
================================

Features
--------
 - Added a new interface,
   twisted.internet.interfaces.IHostnameResolver, which is an
   improvement to twisted.internet.interfaces.IResolverSimple that
   supports resolving multiple addresses as well as resolving IPv6
   addresses.  This is a native, asynchronous, Twisted analogue to
   getaddrinfo. (#4362)
 - twisted.web.client.Agent now uses HostnameEndpoint internally; as a
   consequence, it now supports IPv6, as well as making connections
   faster and more reliably to hosts that have more than one DNS name.
   (#6712)
 - twisted.internet.ssl.CertificateOptions now has the new constructor
   argument 'raiseMinimumTo', allowing you to increase the minimum TLS
   version to this version or Twisted's default, whichever is higher.
   The additional new constructor arguments 'lowerMaximumSecurityTo'
   and 'insecurelyLowerMinimumTo' allow finer grained control over
   negotiated versions that don't honour Twisted's defaults, for
   working around broken peers, at the cost of reducing the security
   of the TLS it will negotiate. (#6800)
 - twisted.internet.ssl.CertificateOptions now sets the OpenSSL
   context's mode to MODE_RELEASE_BUFFERS, which will free the
   read/write buffers on idle TLS connections to save memory. (#8247)
 - trial --help-reactors will only list reactors which can be
   imported.  (#8745)
 - twisted.internet.endpoints.HostnameEndpoint now uses the passed
   reactor's implementation of
   twisted.internet.interfaces.IReactorPluggableResolver to resolve
   hostnames rather than its own deferToThread/getaddrinfo wrapper;
   this makes its hostname resolution pluggable via a public API.
   (#8922)
 - twisted.internet.reactor.spawnProcess now does not emit a
   deprecation warning on Unicode arguments. It will encode Unicode
   arguments down to bytes using the filesystem encoding on UNIX and
   Python 2 on Windows, and pass Unicode through unchanged on Python 3
   on Windows. (#8941)
 - twisted.trial._dist.test.test_distreporter now works on Python 3.
   (#8943)

Bugfixes
--------
 - trial --help-reactors will now display iocp and win32er reactors
   with Python 3. (#8745)
 - twisted.logger._flatten.flattenEvent now handles log_format being
   None instead of assuming the value is always a string. (#8860)
 - twisted.protocol.ftp is now Python 3 compatible (#8865)
 - twisted.names.client.Resolver can now resolve names with IPv6 DNS
   servers. (#8877)
 - twisted.application.internet.ClientService now waits for existing
   connections to disconnect before trying to connect again when
   restarting. (#8899)
 - twisted.internet.unix.Server.doRead and
   twisted.internet.unix.Client.doRead no longer fail if recvmsg's
   ancillary data contains more than one file descriptor. (#8911)
 - twist on Python 3 now correctly prints the help text when given no
   plugin to run. (#8918)
 - twisted.python.sendmsg.sendmsg no longer segfaults on Linux +
   Python 2. (#8969)
 - IHandshakeListener providers connected via SSL4ClientEndpoint will
   now have their handshakeCompleted methods called. (#8973)
 - The twist script now respects the --reactor option. (#8983)
 - Fix crash when using SynchronousTestCase with Warning object which
   does not store a string as its first argument (like
   libmysqlclient). (#9005)
 - twisted.python.compat.execfile() does not open files with the
   deprecated 'U' flag on Python 3. (#9012)

Deprecations and Removals
-------------------------
 - twisted.internet.ssl.CertificateOption's 'method' constructor
   argument is now deprecated, in favour of the new 'raiseMinimumTo',
   'lowerMaximumSecurityTo', and 'insecurelyLowerMinimumTo' arguments.
   (#6800)
 - twisted.protocols.telnet (not to be confused with the supported
   twisted.conch.telnet), deprecated since Twisted 2.5, has been
   removed. (#8925)
 - twisted.application.strports.parse, as well as the deprecated
   default arguments in strports.service/listen, deprecated since
   Twisted 10.2, has been removed. (#8926)
 - twisted.web.client.getPage and twisted.web.client.downloadPage have
   been deprecated in favour of https://pypi.org/project/treq and
   twisted.web.client.Agent. (#8960)
 - twisted.internet.defer.timeout is deprecated in favor of
   twisted.internet.defer.Deferred.addTimeout (#8971)

Other
-----
 - #7879, #8583, #8764, #8809, #8859, #8906, #8910, #8913, #8916,
   #8934, #8945, #8949, #8950, #8952, #8953, #8959, #8962, #8963,
   #8967, #8975, #8976, #8993, #9013


Twisted Conch 17.1.0 (2017-02-04)
=================================

Features
--------
 - twisted.conch.manhole now works on Python 3. (#8327)
 - Twisted Conch now supports ECDH key exchanges. (#8730)
 - Add support in twisted.conch.ssh for hmac-sha2-384 (#8784)
 - conch and cftp scripts now work on Python 3. (#8791)
 - twisted.conch.ssh supports ECDH key exchange. (#8811)

Bugfixes
--------
 - twisted.conch.ssh.keys.Key.fromString now supports OpenSSL private
   keys with Windows line endings (\r\n) again (broken since 16.6.0).
   (#8928)

Improved Documentation
----------------------
 - The documentation for
   twisted.conch.endpoints.SSHCommandClientEndpoint.existingConnection
   now describes where the value for the connection parameter might
   come from. (#8892)

Other
-----
 - #8890, #8894, #8957, #8958, #8968


Twisted Mail 17.1.0 (2017-02-04)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.tap (the twist plugin for mail) no longer accepts the
   --pop3s option or implicit port numbers to --pop3 and --smtp. This
   functionality has been deprecated since 11.0. (#8920)


Twisted Names 17.1.0 (2017-02-04)
=================================

Bugfixes
--------
 - twisted.names.authority.BindAuthority has been ported to Python 3.
   (#8880)


Twisted News 17.1.0 (2017-02-04)
================================

No significant changes have been made for this release.


Twisted Pair 17.1.0 (2017-02-04)
================================

No significant changes have been made for this release.


Twisted Runner 17.1.0 (2017-02-04)
==================================

Bugfixes
--------
 - On Python 3, procmon now handles process output without exceptions
   (#8919)


Twisted Web 17.1.0 (2017-02-04)
===============================

Features
--------
 - twisted.web.client.Agent now sets ``Content-Length: 0`` for PUT and
   POST requests made without a body producer. (#8984)

Bugfixes
--------
 - twisted.web.http.HTTPFactory now times connections out after one
   minute of no data from the client being received, before the
   request is complete, rather than twelve hours. (#3746)
 - twisted.web.http.HTTPChannel, the server class for Twisted's
   HTTP/1.1 server, now exerts backpressure against clients that do
   not read responses. This means that if a client stops reading from
   a socket for long enough, Twisted will stop reading further
   requests from that client until it consumes some responses. (#8868)
 - twisted.web.http_headers.Headers.getRawHeaders no longer attempts
   to decode the default value when called with a unicode header name.
   (#8974)
 - twisted.web.http.HTTPChannel is less likely to leak file
   descriptors when timing out clients using HTTPS connections. In
   some cases it is still possible to leak a file descriptor when
   timing out HTTP clients: further patches will address this issue.
   (#8992)

Other
-----
 - #7744, #8909, #8935


Twisted Words 17.1.0 (2017-02-04)
=================================

No significant changes have been made for this release.


Twisted Core 16.6.0 (2016-11-17)
================================

Features
--------
 - The twist script can now be run by invoking python -m twisted.
   (#8657)
 - twisted.protocols.sip has been ported to Python 3. (#8669)
 - twisted.persisted.dirdbm has been ported to Python 3. (#8888)

Bugfixes
--------
 - twisted.internet.defer.Deferred now implements send, not __send__,
   which means that it is now a conforming generator. (#8861)
 - The IOCP reactor no longer transmits the contents of uninitialized
   memory when writing large amounts of data. (#8870)
 - Deferreds awaited/yielded from in a
   twisted.internet.defer.ensureDeferred wrapped coroutine will now
   properly raise exceptions. Additionally, it more closely models
   asyncio.ensure_future and will pass through Deferreds. (#8878)
 - Deferreds that are paused or chained on other Deferreds will now
   return a result when yielded/awaited in a twisted.internet.defer
   .ensureDeferred-wrapped coroutine, instead of returning the
   Deferred it was chained to. (#8890)

Improved Documentation
----------------------
 - twisted.test.proto_helpers is now explicitly covered by the
   compatibility policy. (#8857)

Other
-----
 - #8281, #8823, #8862


Twisted Conch 16.6.0 (2016-11-17)
=================================

Features
--------
 - twisted.conch.ssh.keys supports ECDSA keys (#8798)
 - scripts/ckeygen can now generate ecdsa keys. (#8828)
 - ckeygen has been ported to Python 3 (#8855)

Deprecations and Removals
-------------------------
 - twisted.conch.ssh no longer uses gmpy, if available. gmpy is
   unmaintained, does not have binary wheels for any platforms, and an
   alternative for higher performance is available in the form of
   PyPy. (#8079)


Twisted Mail 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Names 16.6.0 (2016-11-17)
=================================

No significant changes have been made for this release.


Twisted News 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Pair 16.6.0 (2016-11-17)
================================

No significant changes have been made for this release.


Twisted Runner 16.6.0 (2016-11-17)
==================================

No significant changes have been made for this release.


Twisted Web 16.6.0 (2016-11-17)
===============================

Features
--------
 - twisted.web.server.Site's HTTP/2 server support now emits vastly
   fewer WINDOW_UPDATE frames than previously. (#8681)

Bugfixes
--------
 - twisted.web.Agent now tolerates receiving unexpected status codes
   in the 100 range by discarding them, which is what RFC 7231
   recommends doing. (#8885)
 - twisted.web._http.H2Stream's getHost and getPeer implementations
   now actually return the host and peer instead of None. (#8893)


Twisted Words 16.6.0 (2016-11-17)
=================================

Features
--------
 - twisted.words.protocols.irc has been ported to Python 3 (#6320)


Twisted Core 16.5.0 (2016-10-28)
================================

Features
--------
 - Added twisted.internet.defer.Deferred.addTimeout method to enable
   timeouts of deferreds. (#5786)
 - Perspective Broker (the twisted.spread package) has been ported to
   Python 3 (#7598)
 - 'yield from' can now be used on Deferreds inside generators, when
   the generator is wrapped with
   twisted.internet.defer.ensureDeferred. (#8087)
 - twisted.internet.asyncioreactor has been added, which is a Twisted
   reactor on top of Python 3.4+'s native asyncio reactor. It can be
   selected by passing "--reactor=asyncio" to Twisted tools (twistd,
   Trial, etc) on platforms that support it (Python 3.4+). (#8367)
 - twisted.python.zippath now works on Windows with Python 3. (#8747)
 - twisted.internet.cfreactor is ported to Python 3 and supported on
   2.7 and 3.5+. (#8838)

Bugfixes
--------
 - twisted.internet.test.test_iocp and twisted.internet.test.test_tcp
   have been fixed to work under Python 3 with the Windows IOCP
   reactor (#8631)
 - Arguments to processes on Windows are now passed mbcs-encoded
   arguments.  This prevents process-related tests from hanging on
   Windows with Python 3. (#8735)
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, no longer accept 3DES-
   based cipher suites by default, to defend against SWEET32. (#8781)
 - twisted.logger.jsonFileLogObserver no longer emits non-JSON
   tracebacks into its file; additionally,
   twisted.logger.formatEventAsClassicLogText now includes traceback
   information for the log event it formats. (#8858)
 - twisted.python.version now exports a version of Incremental that is
   16.10.1 or higher, making t.p.v.Version package name comparisons
   case-insensitive. (#8863)
 - twisted.python.reflect.safe_str encodes unicode as ascii with
   backslashreplace error handling on Python 2. (#8864)

Improved Documentation
----------------------
 - The twisted.internet.interfaces.IProtocol.dataReceived() method
   takes one parameter of type bytes.  This has been clarified in the
   doc string. (#8763)

Deprecations and Removals
-------------------------
 - twisted.python.constants is deprecated in preference to constantly
   on PyPI, which is the same code rolled into its own package.
   (#7351)
 - twisted.python.dist3 has been made private API. (#8761)
 - When the source code is checked out, bin/trial is no longer in the
   tree.  Developers working on the Twisted source code itself should
   either (1) run all tests under tox, or (2) run 'python setup.py
   develop' to install trial before running any tests. (#8765)
 - twisted.protocols.gps, deprecated since Twisted 15.2, has been
   removed. (#8787)

Other
-----
 - #4926, #7868, #8209, #8214, #8271, #8308, #8324, #8348, #8367,
   #8377, #8378, #8379, #8380, #8381, #8383, #8385, #8387, #8388,
   #8389, #8391, #8392, #8393, #8394, #8397, #8406, #8410, #8412,
   #8413, #8414, #8421, #8425, #8426, #8430, #8432, #8434, #8435,
   #8437, #8438, #8439, #8444, #8451, #8452, #8453, #8454, #8456,
   #8457, #8459, #8462, #8463, #8465, #8468, #8469, #8479, #8482,
   #8483, #8486, #8490, #8493, #8494, #8496, #8497, #8498, #8499,
   #8501, #8503, #8504, #8507, #8508, #8510, #8513, #8514, #8515,
   #8516, #8517, #8520, #8521, #8522, #8523, #8524, #8527, #8528,
   #8529, #8531, #8532, #8534, #8536, #8537, #8538, #8543, #8544,
   #8548, #8552, #8553, #8554, #8555, #8557, #8560, #8563, #8565,
   #8568, #8569, #8572, #8573, #8574, #8580, #8581, #8582, #8586,
   #8589, #8590, #8592, #8593, #8598, #8603, #8604, #8606, #8609,
   #8615, #8616, #8617, #8618, #8619, #8621, #8622, #8624, #8627,
   #8628, #8630, #8632, #8634, #8640, #8644, #8645, #8646, #8647,
   #8662, #8664, #8666, #8668, #8671, #8672, #8677, #8678, #8684,
   #8691, #8702, #8705, #8706, #8716, #8719, #8724, #8725, #8727,
   #8734, #8741, #8749, #8752, #8754, #8755, #8756, #8757, #8758,
   #8767, #8773, #8776, #8779, #8780, #8785, #8788, #8789, #8790,
   #8792, #8793, #8799, #8808, #8817, #8839, #8845, #8852


Twisted Conch 16.5.0 (2016-10-28)
=================================

Features
--------
 - SSH key fingerprints can be generated using base64 encoded SHA256
   hashes. (#8701)

Bugfixes
--------
 - SSHUserAuthServer does not crash on keyboard interactive
   authentication when running on Python 3 (#8771)
 - twisted.conch.insults.insults.ServerProtocol no longer corrupts a
   client's display when attempting to set the cursor position, and
   its ECMA-48 terminal manipulation works on Python 3. (#8803)

Other
-----
 - #8495, #8511, #8715, #8851


Twisted Mail 16.5.0 (2016-10-28)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.protocols.DomainSMTP and DomainESMTP, deprecated since
   2003, have been removed. (#8772)

Other
-----
 - #6289, #8525, #8786, #8830


Twisted Names 16.5.0 (2016-10-28)
=================================

No significant changes have been made for this release.

Other
-----
 - #8625, #8663


Twisted News 16.5.0 (2016-10-28)
================================

No significant changes have been made for this release.


Twisted Pair 16.5.0 (2016-10-28)
================================

Features
--------
 - twisted.pair has been ported to Python 3 (#8744)


Twisted Runner 16.5.0 (2016-10-28)
==================================

No significant changes have been made for this release.


Twisted Web 16.5.0 (2016-10-28)
===============================

Bugfixes
--------
 - twisted.web.client.HTTPConnectionPool and anything that uses it,
   like twisted.web.client.Agent, have had their logic for resuming
   transports changed so that transports are resumed after state
   machine transitions are complete, rather than before. This change
   allows the HTTP client infrastructure to work with alternative HTTP
   implementations such as HTTP/2 which may be able to deliver a
   complete response synchronously when producing is resumed. (#8720)

Other
-----
 - #8519, #8530, #8629, #8707, #8777, #8778, #8844


Twisted Words 16.5.0 (2016-10-28)
=================================

No significant changes have been made for this release.

Other
-----
 - #8360, #8460


Twisted Core 16.4.1 (2016-09-07)
================================

Features
--------
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, now support ChaCha20
   ciphers when available from the OpenSSL on the system. (#8760)

Bugfixes
--------
 - Client and server TLS connections made via the client TLS endpoint
   and the server SSL endpoint, as well as any other code that uses
   twisted.internet.ssl.CertificateOptions, no longer accept 3DES-
   based cipher suites by default, to defend against SWEET32. (#8781)


Twisted Conch 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted Mail 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Names 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted News 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Pair 16.4.1 (2016-09-07)
================================

No significant changes have been made for this release.


Twisted Runner 16.4.1 (2016-09-07)
==================================

No significant changes have been made for this release.


Twisted Web 16.4.1 (2016-09-07)
===============================

No significant changes have been made for this release.


Twisted Words 16.4.1 (2016-09-07)
=================================

No significant changes have been made for this release.


Twisted Core 16.4.0 (2016-08-25)
================================

Features
--------
 - Add twisted.application.twist, meant to eventually replace twistd
   with a simpler interface.  Add twisted.application.runner API,
   currently private, which twist is built on. (#5705)
 - The new interface IHandshakeListener that can be implemented by any
   Protocol provides a callback that is called when the TLS handshake
   has been completed, allowing Protocols to make decisions about the
   TLS configuration before application data is sent. (#6024)
 - twisted.python.syslog has been ported to Python 3. (#7957)
 - twisted.internet.defer.ensureDeferred has been added, similar to
   asyncio's ensure_future. Wrapping a coroutine (the result of a
   function defined using async def, available only on Python 3.5+)
   with it allows you to use the "await" keyword with Deferreds inside
   the coroutine, similar to "yield" when using inlineCallbacks.
   (#8088)
 - twisted.internet.inotify have been ported to Python 3 (#8211)
 - twisted.enterprise has been ported to Python 3. The third-party
   pysqlite2 package has not been ported to Python 3, so any database
   connector based on pysqlite2 cannot be used. Instead the sqlite3
   module included with Python 3 should be used. (#8303)
 - Scripts such as cftp, ckeygen, conch, mailmail, pyhtmlizer,
   tkconch, twistd and trial have been updated to be setuptools
   console scripts.  (#8491)
 - twisted.pair.raw and twisted.pair.rawudp have been ported to Python
   3 (#8545)
 - twisted.internet.baseprocess has been ported to Python 3. (#8546)
 - twisted.python.dist has been ported to Python 3 (#8556)
 - twisted.internet.interfaces.IOpenSSLContextFactory has been added,
   which defines the interface provided both by the old-style
   twisted.internet.ssl.ContextFactory class and the newer
   twisted.interface.ssl.CertificateOptions class. This is a precursor
   to formally deprecating the former class in favour of the latter.
   (#8597)
 - twisted.python.zipstream has been ported to Python 3 (#8607)
 - Zip file entries returned by ChunkingZipFile.readfile() are now
   context managers. (#8641)
 - twisted.protocols.socks has been ported to Python 3 (#8665)
 - twisted.spread.banana has been ported to Python 3 (#8667)
 - Trial can now be invoked via "python -m twisted.trial". (#8712)
 - twisted.protocols.postfix has been ported to Python 3 (#8713)
 - twisted.protocols.wire and twisted.protocols.portforwarding have
   been ported to Python 3 (#8717)
 - twisted.protocols.stateful has been ported to Python 3 (#8718)
 - twisted.protocols.memcache is now compatible with Python 3. (#8726)
 - twisted.protocols.dict has been ported to Python 3 (#8732)

Bugfixes
--------
 - pip install -e ".[dev]" now works on Python 3, but it will not
   install twistedchecker or pydoctor, which have not yet been ported.
   (#7807)
 - twistd can now properly daemonize on Linux/Unix when run under
   Python3 and will not hang indefinitely. (#8155)
 - tox can now be used to run Twisted's tests on Windows (#8578)
 - twisted.python.filepath.setContent() and
   twisted.python.filepath.moveTo() now work on Windows with Python 3
   (#8610)
 - twisted.internet.win32eventreactor works on Python 3 in Windows
   (#8626)
 - The TLS payload buffer size was reduced in
   twisted.protocols.tls.TLSMemoryBIOProtocol.  This fixes writing of
   very long strings using the TLSv1_1 method from the OpenSSL
   library. (#8693)
 - twisted.logger._flatten.flattenEvent() now does not crash if passed
   a unicode string. (#8699)
 - twisted.application.strports.service (and thus twistd) no longer
   swallow asynchronous exceptions from IStreamServerEndpoint.listen.
   (#8710)
 - _twistd_unix now reports the name and encoded message of an
   exception raised during daemonization on Python 2 and 3. (#8731)
 - twisted.protocols.amp now handles floats on Python 3. Previously,
   sending a float would raise a ValueError. (#8746)

Improved Documentation
----------------------
 - Some broken links to xprogramming in the unit test documentation
   have been fixed. (#8579)
 - The Twisted Tutorial "The Evolution of Finger" has been updated to
   use endpoints throughout. (#8588)
 - Updated the mail examples to use endpoints and better TLS. (#8595)
 - Changed the Twisted Web howto to use endpoints and modern TLS.
   (#8596)
 - Updated bug report URL in man pages. (#8600)
 - In twisted.internet.udp.Port, write() takes a parameter of type
   bytes.  This is clarified in the docstring. (#8635)
 - twisted.internet.interfaces.ITransport.write() and
   twisted.internet.interfaces.ITransport.writeSequence() take bytes
   parameters. (#8636)
 - twisted.python.filepath.AbstractFilePath.getContent() returns
   bytes.  The docstring was updated to clarify this. (#8637)
 - Updated release notes to reflect that 15.4 is the last version that
   supported Python 2.6, not 15.5. (#8651)
 - A missing space in defer.rst resulted in badly rendered output. The
   space was added. (#8723)

Deprecations and Removals
-------------------------
 - Dropped support for pyOpenSSL versions less than 16.0.0. (#8441)

Other
-----
 - #4926, #7868, #8209, #8271, #8276, #8308, #8324, #8348, #8367,
   #8377, #8378, #8379, #8380, #8381, #8383, #8385, #8386, #8387,
   #8388, #8389, #8391, #8392, #8393, #8394, #8397, #8406, #8410,
   #8412, #8413, #8414, #8421, #8425, #8426, #8428, #8429, #8430,
   #8432, #8434, #8435, #8437, #8438, #8439, #8444, #8451, #8452,
   #8453, #8454, #8456, #8457, #8459, #8462, #8463, #8465, #8468,
   #8469, #8479, #8482, #8483, #8486, #8490, #8493, #8494, #8496,
   #8497, #8498, #8499, #8501, #8503, #8504, #8507, #8508, #8510,
   #8513, #8514, #8515, #8516, #8517, #8520, #8521, #8522, #8523,
   #8524, #8527, #8528, #8529, #8531, #8532, #8534, #8536, #8537,
   #8538, #8540, #8541, #8543, #8548, #8552, #8553, #8554, #8555,
   #8557, #8560, #8563, #8565, #8568, #8569, #8572, #8573, #8574,
   #8577, #8580, #8581, #8582, #8584, #8586, #8589, #8590, #8592,
   #8593, #8598, #8603, #8604, #8606, #8609, #8615, #8616, #8617,
   #8618, #8619, #8621, #8624, #8627, #8628, #8630, #8632, #8634,
   #8640, #8644, #8645, #8646, #8647, #8648, #8662, #8664, #8666,
   #8668, #8671, #8672, #8684, #8691, #8702, #8703, #8705, #8706,
   #8716, #8719, #8724, #8725, #8727, #8733, #8734, #8741


Twisted Conch 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.conch.ssh.address is now ported to Python 3. (#8495)
 - twisted.conch.ssh.transport is now ported to Python 3. (#8638)
 - twisted.conch.ssh.channel is now ported to Python 3. (#8649)
 - twisted.conch.ssh.userauth is now ported to Python 3. (#8654)
 - twisted.conch.ssh.connection is now ported to Python 3. (#8660)
 - twisted.conch.ssh.session is now ported to Python 3. (#8661)
 - twisted.conch.ssh.filetransfer is now ported to Python 3. (#8675)
 - twisted.conch.ssh.agent is now ported to Python 3. (#8686)
 - twisted.conch.ssh is now ported to Python 3. (#8690)
 - twisted.conch.openssh_compat.* is now ported to Python 3. (#8694)
 - twisted.conch.client.knownhosts is now ported to Python 3. (#8697)
 - twisted.conch.insults.insults has been ported to Python 3 (#8698)
 - twisted.conch.client.default is now ported to Python 3. (#8700)
 - twisted.conch.recvline has been ported to Python 3 (#8709)
 - twisted.conch.endpoints is now ported to Python 3. (#8722)

Bugfixes
--------
 - The SSHService is now a bytestring (#8653)
 - The name field in SShChannel is now a bytestring (#8683)

Improved Documentation
----------------------
 - Fixed syntax errors in cftp man page. (#8601)

Other
-----
 - #8495, #8511, #8715


Twisted Mail 16.4.0 (2016-08-25)
================================

Deprecations and Removals
-------------------------
 - twisted.mail.mail.DomainWithDefaultDict.has_key is now deprecated
   in favor of the `in` keyword. (#8361)
 - twisted.mail.protocols.SSLContextFactory, deprecated since Twisted
   12.0, has been removed. (#8591)

Other
-----
 - #8525


Twisted Names 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.names.srvconnect is now ported to Python 3. (#8262)
 - twisted.names.resolve and twisted.names.tap have been ported to
   Python 3 (#8550)

Other
-----
 - #8625, #8663


Twisted News 16.4.0 (2016-08-25)
================================

No significant changes have been made for this release.


Twisted Pair 16.4.0 (2016-08-25)
================================

No significant changes have been made for this release.


Twisted Runner 16.4.0 (2016-08-25)
==================================

Features
--------
 - twisted.runner has been ported to Python 3. (#8739)


Twisted Web 16.4.0 (2016-08-25)
===============================

Features
--------
 - Twisted web HTTP/2 servers now time out HTTP/2 connections in the
   same manner as HTTP/1.1 connections. (#8480)

Bugfixes
--------
 - A bug in twisted.web.server.Site.makeSession which may lead to
   predictable session IDs was fixed.  Session IDs are now generated
   securely using `os.urandom`. (#3460)
 - twisted.web.server.Request.getSession will now, for a request sent
   over HTTPS, set a "Secure" cookie, preventing the secure session
   from being sent over plain-text HTTP. (#3461)
 - If called multiple times, twisted.web.http.Request.setLastModified
   now correctly observes the greatest supplied value. (#3807)
 - The HTTP server now correctly times connections out. (broken in
   16.2) (#8481)
 - Twisted's HTTP/2 support no longer throws priority exceptions when
   WINDOW_UDPATE frames are received after a response has been
   completed. (#8558)
 - twisted.web.twcgi.CGIScript will now not pass the "Proxy" header to
   CGI scripts, as a mitigation to CVE-2016-1000111. (#8623)
 - Twisted Web's HTTP/2 server can now tolerate streams being reset by
   the client midway through a data upload without throwing
   exceptions. (#8682)
 - twisted.web.http.Request now swallows header writes on reset HTTP/2
   streams, rather than erroring out. (#8685)
 - twisted.web's HTTP/2 server now tolerates receiving WINDOW_UPDATE
   frames for streams for which it has no outstanding data to send.
   (#8695)
 - twisted.web.http.HTTPChannel now resumes producing on finished,
   non-persistent connections. This prevents HTTP/1 servers using TLS
   from leaking a CLOSE_WAIT socket per request. (#8766)

Other
-----
 - #8519, #8530, #8629, #8707


Twisted Words 16.4.0 (2016-08-25)
=================================

Features
--------
 - twisted.words.xish is now ported to Python 3 (#8337)
 - twisted.words.protocols.jabber is now ported to Python 3 (#8423)
 - twisted.words.protocols.irc.ERR_TOOMANYMATCHES was introduced
   according to the RFC 2812 errata. (#8585)

Bugfixes
--------
 - twisted.words.protocols.irc.RPL_ADMINLOC was removed and replaced
   with twisted.words.protocols.irc.RPL_ADMINLOC1 and
   twisted.words.protocols.irc.RPL_ADMINLOC2 to match the admin
   commands defined in RFC 2812. (#8585)
 - twisted.words.protocols.jabber.sasl_mechanisms has been fixed for
   Python 3.3 (#8738)

Improved Documentation
----------------------
 - The XMPP client example now works on Python 3. (#8509)

Other
-----
 - #8360, #8460


Twisted Core 16.3.0 (2016-07-05)
================================

Features
--------
 - Defined a new interface, IProtocolNegotiationFactory, that can be
   implemented by IOpenSSLClientConnectionCreator or
   IOpenSSLServerConnectionCreator factories to allow them to offer
   protocols for negotiation using ALPN or NPN during the TLS
   handshake. (#8188)
 - twisted.trial.unittest.SynchronousTestCase.assertRegex is now
   available to provide Python 2.7 and Python 3 compatibility. (#8372)

Improved Documentation
----------------------
 - Development documentation has been updated to refer to Git instead
   of SVN. (#8335)

Deprecations and Removals
-------------------------
 - twisted.python.reflect's deprecated functions have been removed.
   This includes funcinfo (deprecated since Twisted 2.5), allYourBase
   and accumulateBases (deprecated since Twisted 11.0), getcurrent and
   isinst (deprecated since Twisted 14.0). (#8293)
 - twisted.scripts.tap2deb and twisted.scripts.tap2rpm (along with the
   associated executables), deprecated since Twisted 15.2, have now
   been removed. (#8326)
 - twisted.spread.ui has been removed. (#8329)
 - twisted.manhole -- not to be confused with manhole in Conch -- has
   been removed. This includes the semi-functional Glade reactor, the
   manhole application, and the manhole-old twistd plugin. (#8330)
 - twisted.protocols.sip.DigestAuthorizer, BasicAuthorizer, and
   related functions have been removed. (#8445)

Other
-----
 - #7229, #7826, #8290, #8323, #8331, #8336, #8341, #8344, #8345,
   #8347, #8351, #8363, #8365, #8366, #8374, #8382, #8384, #8390,
   #8395, #8396, #8398, #8399, #8400, #8401, #8403, #8404, #8405,
   #8407, #8408, #8409, #8415, #8416, #8417, #8418, #8419, #8420,
   #8427, #8433, #8436, #8461


Twisted Conch 16.3.0 (2016-07-05)
=================================

No significant changes have been made for this release.


Twisted Mail 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Names 16.3.0 (2016-07-05)
=================================

Bugfixes
--------
 - twisted.names.client.Resolver as well as all resolvers inheriting
   from twisted.names.common.ResolverBase can now understand DNS
   answers that come back in a different case than the query. Example:
   querying for www.google.com and the answer comes back with an A
   record for www.google.COM will now work. (#8343)


Twisted News 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Pair 16.3.0 (2016-07-05)
================================

No significant changes have been made for this release.


Twisted Runner 16.3.0 (2016-07-05)
==================================

No significant changes have been made for this release.


Twisted Web 16.3.0 (2016-07-05)
===============================

Features
--------
 - twisted.web.http.HTTPChannel now implements ITransport. Along with
   this change, twisted.web.http.Request now directs all its writes to
   the HTTPChannel, rather than to the backing transport. This change
   is required for future HTTP/2 work. (#8191)
 - twisted.web.http.HTTPChannel now has a HTTP/2 implementation which
   will be used if the transport has negotiated using it through
   ALPN/NPN (see #8188). (#8194)

Bugfixes
--------
 - twisted.web.client.Agent and twisted.web.client.ProxyAgent now add
   brackets to IPv6 literal addresses in the host header they send.
   (#8369)
 - The HTTP server now correctly times connections out. (broken in
   16.2) (#8481)

Deprecations and Removals
-------------------------
 - twisted.web would previously dispatch pipelined requests
   simultaneously and queue the responses. This behaviour did not
   enforce any of the guarantees required by RFC 7230 or make it
   possible for users to enforce those requirements. For this reason,
   the parallel dispatch of requests has been removed. Pipelined
   requests are now processed serially. (#8320)


Twisted Words 16.3.0 (2016-07-05)
=================================

No significant changes have been made for this release.


Twisted Core 16.2.0 (2016-05-18)
================================

Features
--------
 - twisted.protocols.haproxy.proxyEndpoint provides an endpoint that
   wraps any other stream server endpoint with the PROXY protocol that
   retains information about the original client connection handled by
   the proxy; this wrapper is also exposed via the string description
   prefix 'haproxy'; for example 'twistd web --port haproxy:tcp:8765'.
   (#8203)
 - twisted.application.app.AppLogger (used by twistd) now uses the new
   logging system. (#8235)

Bugfixes
--------
 - twisted.application-using applications (trial, twistd, etc) now
   work with the --reactor option on Python 3. (#8299)
 - Failures are now logged by STDLibLogObserver. (#8316)

Improved Documentation
----------------------
 - Deprecation documentation was extended to include a quick check
   list for developers. (#5645)
 - The Twisted Deprecation Policy is now documented in the Twisted
   Development Policy. (#8082)
 - The documentation examples for UDP now work on Python 3. (#8280)

Deprecations and Removals
-------------------------
 - Passing a factory that produces log observers that do not implement
   twisted.logger.ILogObserver or twisted.python.log.ILogObserver to
   twisted.application.app.AppLogger has been deprecated. This is
   primarily used by twistd's --logger option. Please use factories
   that produce log observers implementing twisted.logger.ILogObserver
   or the legacy twisted.python.log.ILogObserver. (#8235)
 - twisted.internet.qtreactor, a stub that imported the external
   qtreactor, has been removed. (#8288)

Other
-----
 - #6266, #8231, #8244, #8256, #8266, #8269, #8275, #8277, #8286,
   #8291, #8292, #8304, #8315


Twisted Conch 16.2.0 (2016-05-18)
=================================

No significant changes have been made for this release.

Other
-----
 - #8279


Twisted Mail 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Names 16.2.0 (2016-05-18)
=================================

Features
--------
 - twisted.names.server is now ported to Python 3 (#8195)
 - twisted.names.authority and twisted.names.secondary have been
   ported to Python 3 (#8259)


Twisted News 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Pair 16.2.0 (2016-05-18)
================================

No significant changes have been made for this release.


Twisted Runner 16.2.0 (2016-05-18)
==================================

Deprecations and Removals
-------------------------
 - twisted.runner.inetdtap and twisted.runner.inetdconf RPC support
   was deprecated as it was broken for a long time. (#8123)


Twisted Web 16.2.0 (2016-05-18)
===============================

Features
--------
 - twisted.web.http.HTTPFactory's constructor now accepts a reactor
   argument, for explicit reactor selection. (#8246)

Bugfixes
--------
 - twisted.web.http.HTTPChannel.headerReceived now respond with 400
   and disconnect when a malformed header is received. (#8101)
 - twisted.web.http.Request once again has a reference to the
   HTTPFactory which created it, the absence of which was preventing
   log messages from being created.  (#8272)
 - twisted.web.http.HTTPChannel no longer processes requests that have
   invalid headers as the final header in their header block. (#8317)
 - twisted.web.client.HTTPClientFactory (and the getPage and
   downloadPage APIs) now timeouts correctly on TLS connections where
   the remote party is not responding on the connection. (#8318)

Other
-----
 - #8300


Twisted Words 16.2.0 (2016-05-18)
=================================

Deprecations and Removals
-------------------------
 - twisted.words.protocols.msn, deprecated since Twisted 15.1, has
   been removed. (#8253)
 - twisted.words.protocols.oscar is deprecated. (#8260)


Twisted Core 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Conch 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted Mail 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Names 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted News 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Pair 16.1.1 (2016-04-08)
================================

No significant changes have been made for this release.


Twisted Runner 16.1.1 (2016-04-08)
==================================

No significant changes have been made for this release.


Twisted Web 16.1.1 (2016-04-08)
===============================

Bugfixes
--------
 - twisted.web.http.Request once again has a reference to the
   HTTPFactory which created it, the absence of which was preventing
   log messages from being created.  (#8272)


Twisted Words 16.1.1 (2016-04-08)
=================================

No significant changes have been made for this release.


Twisted Core 16.1.0 (2016-04-04)
================================

Features
--------
 - twisted.application.internet.ClientService, a service that
   maintains a persistent outgoing endpoint-based connection; a
   replacement for ReconnectingClientFactory that uses modern APIs.
   (#4735)
 - Twisted now uses setuptools' sdist to build tarballs. (#7985)

Bugfixes
--------
 - Twisted is now compatible with OpenSSL 1.0.2f. (#8189)

Other
-----
 - #4543, #8124, #8193, #8210, #8220, #8223, #8226, #8242


Twisted Conch 16.1.0 (2016-04-04)
=================================

Features
--------
 - twisted.conch.checkers is now ported to Python 3. (#8225)
 - twisted.conch.telnet is now ported to Python 3. (#8228)
 - twisted.conch.manhole_ssh.ConchFactory (used by `twistd manhole`)
   no longer uses a hardcoded SSH server key, and will generate a
   persistent one, saving it in your user appdir. If you use
   ConchFactory, you will now need to provide your own SSH server key.
   (#8229)

Other
-----
 - #8237, #8240


Twisted Mail 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Names 16.1.0 (2016-04-04)
=================================

No significant changes have been made for this release.


Twisted News 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Pair 16.1.0 (2016-04-04)
================================

No significant changes have been made for this release.


Twisted Runner 16.1.0 (2016-04-04)
==================================

No significant changes have been made for this release.


Twisted Web 16.1.0 (2016-04-04)
===============================

Features
--------
 - twisted.web.http.Request.addCookie now supports both unicode and
   bytes arguments, with unicode arguments being encoded to UTF-8.
   (#8067)

Bugfixes
--------
 - twisted.web.util.DeferredResource no longer causes spurious
   "Unhandled error in Deferred" log messages. (#8192)
 - twisted.web.server.site.makeSession now generates an uid of type
   bytes on both Python 2 and 3. (#8215)

Other
-----
 - #8238


Twisted Words 16.1.0 (2016-04-04)
=================================

No significant changes have been made for this release.


Twisted Core 16.0.0 (2016-03-10)
================================

Features
--------
 - todo parameter for IReporter.addExpectedSuccess and
   IReporter.addUnexpectedSuccess is no longer required. If not
   provided, a sensible default will be used instead. (#4811)
 - A new string endpoint type, "tls:", allows for properly-verified
   TLS (unlike "ssl:", always matching hostname resolution with
   certificate hostname verification) with faster IPv4/IPv6
   connections.  This comes with an accompanying function,
   twisted.internet.endpoints.wrapClientTLS, which can wrap an
   arbitrary client endpoint with client TLS. (#5642)
 - twisted.python.filepath.makedirs accepts an ignoreExistingDirectory
   flag which ignore the OSError raised by os.makedirs if requested
   directory already exists. (#5704)
 - twisted.protocols.amp has been ported to Python 3. (#6833)
 - twisted.internet.ssl.trustRootFromCertificates returns an object
   suitable for use as trustRoot= to
   twisted.internet.ssl.optionsForClientTLS that trusts multiple
   certificates. (#7671)
 - twisted.python.roots is now ported to Python 3. (#8131)
 - twisted.cred.strports has been ported to Python 3. (#8216)

Bugfixes
--------
 - Expected failures from standard library unittest no longer fail
   with Trial reporters. (#4811)
 - twisted.internet.endpoints.HostnameEndpoint.connect no longer fails
   with an AlreadyCalledError when the Deferred it returns is
   cancelled after all outgoing connection attempts have been made but
   none have yet succeeded or failed. (#8014)
 - twisted.internet.task.LoopingCall.withCount when run with internal
   of 0, now calls the countCallable with 1, regardless of the time
   passed between calls. (#8125)
 - twisted.internet.endpoints.serverFromString, when parsing a SSL
   strports definition, now gives the correct error message when an
   empty chain file is given. (#8222)

Improved Documentation
----------------------
 - The Twisted Project has adopted the Contributor Covenant as its
   Code of Conduct. (#8173)

Deprecations and Removals
-------------------------
 - twisted.internet.task.LoopingCall.deferred is now deprecated. Use
   the deferred returned by twisted.internet.task.LoopingCall.start()
   (#8116)
 - twisted.internet.gtkreactor, the GTK+ 1 reactor deprecated since
   Twisted 10.1, has been removed. This does not affect the GTK2,
   GLib, GTK3, or GObject-Introspection reactors. (#8145)
 - twisted.protocols.mice, containing a Logitech MouseMan serial
   driver, has been deprecated. (#8148)
 - The __version__ attribute of former subprojects (conch, mail,
   names, news, pair, runner, web, and words) is deprecated in
   preference to the central twisted.__version__. (#8219)

Other
-----
 - #6842, #6978, #7668, #7791, #7881, #7943, #7944, #8050, #8104,
   #8115, #8119, #8122, #8139, #8144, #8154, #8162, #8180, #8187,
   #8220


Twisted Conch 16.0.0 (2016-03-10)
=================================

Features
--------
 - twisted.conch now uses cryptography instead of PyCrypto for its
   underlying crypto operations. (#7413)
 - twisted.conch.ssh.keys is now ported to Python 3. (#7998)

Bugfixes
--------
 - twisted.conch.ssh.channel.SSHChannel's getPeer and getHost methods
   now return an object which provides IAddress instead of an old-
   style tuple address. (#5999)
 - twisted.conch.endpoint.SSHCommandClientEndpoint, when
   authentication is delegated to an SSH agent, no longer leaves the
   agent connection opened when connection to the server is lost.
   (#8138)

Other
-----
 - #7037, #7715, #8200, #8208


Twisted Mail 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Names 16.0.0 (2016-03-10)
=================================

No significant changes have been made for this release.


Twisted News 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Pair 16.0.0 (2016-03-10)
================================

No significant changes have been made for this release.


Twisted Runner 16.0.0 (2016-03-10)
==================================

No significant changes have been made for this release.


Twisted Web 16.0.0 (2016-03-10)
===============================

Features
--------
 - twisted.web.http_headers._DictHeaders now correctly handles
   updating via keyword arguments in Python 3 (therefore
   twisted.web.http_headers is now fully ported to Python 3). (#6082)
 - twisted.web.wsgi has been ported to Python 3. (#7993)
 - twisted.web.http_headers.Headers now accepts both Unicode and
   bytestring keys and values, encoding to iso-8859-1 and utf8
   respectively. (#8129)
 - twisted.web.vhost ported to Python 3. (#8132)

Bugfixes
--------
 - twisted.web.http.HTTPChannel now correctly handles non-ascii method
   name by returning 400. Previously non-ascii method name was causing
   unhandled exceptions. (#8102)
 - twisted.web.static.File on Python 3 now redirects paths to
   directories without a trailing slash, to a path with a trailing
   slash, as on Python 2. (#8169)

Deprecations and Removals
-------------------------
 - twisted.web.http.Request's headers and received_headers attributes,
   deprecated since Twisted 13.2, have been removed. (#8136)
 - twisted.web.static.addSlash is deprecated. (#8169)

Other
-----
 - #8140, #8182


Twisted Words 16.0.0 (2016-03-10)
=================================

No significant changes have been made for this release.


Twisted Core 15.5.0 (2015-11-28)
================================

Python 3.5 (on POSIX) support has been added.

This release introduces changes that are required for Conch's SSH
implementation to work with OpenSSH 6.9+ servers.

Features
--------
 - twisted.python.url is a new abstraction for URLs, supporting RFC
   3987 IRIs. (#5388)
 - twisted.python.logfile is now ported to Python 3. (#6749)
 - twisted.python.zippath has been ported to Python 3. (#6917)
 - twisted.internet.ssl.CertificateOptions and
   twisted.internet.ssl.optionsForClientTLS now take a
   acceptableProtocols parameter that enables negotiation of the next
   protocol to speak after the TLS handshake has completed. This field
   advertises protocols over both NPN and ALPN. Also added new
   INegotiated interface for TLS interfaces that support protocol
   negotiation. This interface adds a negotiatedProtocol property that
   reports what protocol, if any, was negotiated in the TLS handshake.
   (#7860)
 - twisted.python.urlpath.URLPath now operates correctly on Python 3,
   using bytes instead of strings, and introduces the fromBytes
   constructor to assist with creating them cross-version. (#7994)
 - twisted.application.strports is now ported to Python 3. (#8011)
 - twistd (the Twisted Daemon) is now ported to Python 3. (#8012)
 - Python 3.5 is now supported on POSIX platforms. (#8042)
 - twisted.internet.serialport is now ported on Python 3. (#8099)

Bugfixes
--------
 - twisted.logger.formatEvent now can format an event if it was
   flattened (twisted.logger.eventAsJSON does this) and has text after
   the last replacement field. (#8003)
 - twisted.cred.checkers.FilePasswordDB now logs an error if the
   credentials db file does not exist, no longer raises an unhandled
   error. (#8028)
 - twisted.python.threadpool.ThreadPool now properly starts enough
   threads to do any work scheduled before ThreadPool.start() is
   called, such as when work is scheduled in the reactor via
   reactor.callInThread() before reactor.run(). (#8090)

Improved Documentation
----------------------
 - Twisted Development test standard documentation now contain
   information about avoiding test data files. (#6535)
 - The documentation for twisted.internet.defer.DeferredSemaphore now
   describes the actual usage for limit and tokens instance
   attributes. (#8024)

Deprecations and Removals
-------------------------
 - twisted.python._initgroups, a C extension, has been removed and
   stdlib support is now always used instead. (#5861)
 - Python 2.6 is no longer supported. (#8017)
 - twisted.python.util.OrderedDict is now deprecated, and uses of it
   in Twisted are replaced with collections.OrderedDict. (#8051)
 - twisted.persisted.sob.load, twisted.persisted.sob.loadValueFromFile
   and twisted.persisted.sob.Persistent.save() are now deprecated when
   used with a passphrase. The encyption used by these methods are
   weak. (#8081)
 - twisted.internet.interfaces.IStreamClientEndpointStringParser has
   been removed and Twisted will no longer use parsers implementing
   this interface. (#8094)

Other
-----
 - #5976, #6628, #6894, #6980, #7228, #7693, #7731, #7997, #8046,
   #8054, #8056, #8060, #8063, #8064, #8068, #8072, #8091, #8095,
   #8096, #8098, #8106


Twisted Conch 15.5.0 (2015-11-18)
=================================

Features
--------
 - twisted.conch.ssh now supports the diffie-hellman-group-exchange-
   sha256 key exchange algorithm. (#7672)
 - twisted.conch.ssh now supports the diffie-hellman-group14-sha1 key
   exchange algorithm. (#7717)
 - twisted.conch.ssh.transport.SSHClientTransport now supports Diffie-
   Hellman key exchange using MSG_KEX_DH_GEX_REQUEST as described in
   RFC 4419. (#8100)
 - twisted.conch.ssh now supports the hmac-sha2-256 and hmac-sha2-512
   MAC algorithms. (#8108)

Deprecations and Removals
-------------------------
 - twisted.conch.ssh.keys.objectType is now deprecated. Use
   twisted.conch.ssh.keys.Key.sshType. (#8080)
 - twisted.conch.ssh.transport.SSHClientTransport no longer supports
   Diffie-Hellman key exchange using MSG_KEX_DH_GEX_REQUEST_OLD for
   pre RFC 4419 servers. (#8100)


Twisted Mail 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Names 15.5.0 (2015-11-18)
=================================

No significant changes have been made for this release.


Twisted News 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Pair 15.5.0 (2015-11-18)
================================

No significant changes have been made for this release.


Twisted Runner 15.5.0 (2015-11-18)
==================================

No significant changes have been made for this release.


Twisted Web 15.5.0 (2015-11-18)
================================

Features
--------
 - twisted.web.http.Request.addCookie now supports the httpOnly
   attribute which when set on cookies prevents the browser exposing
   it through channels other than HTTP and HTTPS requests (i.e. they
   will not be accessible through JavaScript). (#5911)
 - twisted.web.client.downloadPage is now ported to Python 3. (#6197)
 - twisted.web.client.Agent is now ported to Python 3. (#7407)
 - twisted.web.tap (ran when calling `twistd web`) has now been ported
   to Python 3. Not all features are enabled -- CGI, WSGI, and
   distributed web serving will be enabled in their respective tickets
   as they are ported. (#8008)

Bugfixes
--------
 - twisted.web.client.URI now supports IPv6 addresses. Previously this
   would mistake the colons used as IPv6 address group separators as
   the start of a port specification. (#7650)
 - twisted.web.util's failure template has been moved inline to work
   around Python 3 distribution issues. (#8047)
 - twisted.web.http.Request on Python 3 now handles multipart/form-
   data requests correctly. (#8052)

Other
-----
 - #8016, #8070


Twisted Words 15.5.0 (2015-11-18)
=================================

Features
--------
 - twisted.words.protocol.irc.IRC now has a sendCommand() method which
   can send messages with tags. (#6667)

Other
-----
 - #8015, #8097


Twisted Core 15.4.0 (2015-09-04)
================================

This is the last Twisted release where Python 2.6 is supported, on any
platform. 

Features
--------
 - Trial has been ported to Python 3. (#5965)
 - Twisted now requires setuptools for installation. (#7177)
 - twisted.internet.endpoints.clientFromString is now ported to Python
   3. (#7973)
 - twisted.internet._sslverify now uses SHA256 instead of MD5 for
   certificate request signing by default. (#7979)
 - twisted.internet.endpoints.serverFromString is now ported to Python
   3. (#7982)
 - twisted.positioning is now ported to Python 3. (#7987)
 - twisted.python.failure.Failure's __repr__ now includes the
   exception message. (#8004)

Bugfixes
--------
 - fixed a bug which could lead to a hang at shutdown in
   twisted.python.threadpool. (#2673)
 - twisted.internet.kqreactor on Python 3 now supports EINTR
   (Control-C) gracefully. (#7887)
 - Fix a bug introduced in 15.3.0; pickling a lambda function after
   importing twisted.persisted.styles raises PicklingError rather than
   AttributeError. (#7989)

Other
-----
 - #7902, #7980, #7990, #7992


Twisted Conch 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.

Other
-----
 - #7977


Twisted Mail 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Names 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.


Twisted News 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Pair 15.4.0 (2015-09-04)
================================

No significant changes have been made for this release.


Twisted Runner 15.4.0 (2015-09-04)
==================================

No significant changes have been made for this release.


Twisted Web 15.4.0 (2015-09-04)
===============================

Features
--------
 - twisted.web.proxy is now ported to Python 3. (#7939)
 - twisted.web.guard is now ported to Python 3. (#7974)

Bugfixes
--------
 - twisted.web.http.Request.setResponseCode now only allows bytes
   messages. (#7981)
 - twisted.web.server.Request.processingFailed will now correctly
   write out the traceback on Python 3. (#7996)


Twisted Words 15.4.0 (2015-09-04)
=================================

No significant changes have been made for this release.


Twisted Core 15.3.0 (2015-08-04)
================================

Features
--------
 - twisted.application.app is now ported to Python 3 (#6914)
 - twisted.plugin now supports Python 3 (#7182)
 - twisted.cred.checkers is now ported to Python 3. (#7834)
 - twisted.internet.unix is now ported to Python 3. (#7874)
 - twisted.python.sendmsg has now been ported to Python 3, using the
   stdlib sendmsg/recvmsg functionality when available. (#7884)
 - twisted.internet.protocol.Factory now uses the new logging system
   (twisted.logger) for all its logging statements. (#7897)
 - twisted.internet.stdio is now ported to Python 3. (#7899)
 - The isDocker method has been introduced on
   twisted.python.runtime.Platform to detect if the running Python is
   inside a Docker container. Additionally, Platform.supportsINotify()
   now returns False if isDocker() is True, because of many Docker
   storage layers having broken INotify. (#7968)

Bugfixes
--------
 - twisted.logger.LogBeginner.beginLoggingTo now outputs the correct
   warning when it is called more than once. (#7916)

Deprecations and Removals
-------------------------
 - twisted.cred.pamauth (providing PAM support) has been removed due
   to it being unusable in current supported Python versions. (#3728)
 - twisted.application.app.HotshotRunner (twistd's hotshot profiler
   module) is removed and twistd now uses cProfile by default. (#5137)
 - twisted.python.win32.getProgramsMenuPath and
   twisted.python.win32.getProgramFilesPath are now deprecated.
   (#7883)
 - twisted.lore has now been removed, in preference to Sphinx. (#7892)
 - Deprecated zsh tab-complete files are now removed in preference to
   twisted.python.usage's tab-complete functionality. (#7898)
 - twisted.python.hashlib, deprecated since 13.1, has now been
   removed. (#7905)
 - twisted.trial.runner.DryRunVisitor, deprecated in Twisted 13.0, has
   now been removed. (#7919)
 - twisted.trial.util.getPythonContainers, deprecated since Twisted
   12.3, is now removed. (#7920)
 - Twisted no longer supports being packaged as subprojects. (#7964)

Other
-----
 - #6136, #7035, #7803, #7817, #7827, #7844, #7876, #7906, #7908,
   #7915, #7931, #7940, #7967, #7983


Twisted Conch 15.3.0 (2015-08-04)
=================================

Bugfixes
--------
 - The Conch Unix server now sets the HOME environment variable when
   executing commands. (#7936)

Other
-----
 - #7937


Twisted Mail 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Names 15.3.0 (2015-08-04)
=================================

No significant changes have been made for this release.


Twisted News 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Pair 15.3.0 (2015-08-04)
================================

No significant changes have been made for this release.


Twisted Runner 15.3.0 (2015-08-04)
==================================

No significant changes have been made for this release.


Twisted Web 15.3.0 (2015-08-04)
===============================

Features
--------
 - twisted.web.xmlrpc is now ported to Python 3. (#7795)
 - twisted.web.template and twisted.web.util are now ported to Python
   3. (#7811)
 - twisted.web.error is now ported to Python 3. (#7845)

Deprecations and Removals
-------------------------
 - twisted.web.html is now deprecated in favor of
   twisted.web.template. (#4948)

Other
-----
 - #7895, #7942, #7949, #7952, #7975


Twisted Words 15.3.0 (2015-08-04)
=================================

No significant changes have been made for this release.


Twisted Core 15.2.1 (2015-05-23)
================================

Bugfixes
--------
 - twisted.logger now marks the `isError` key correctly on legacy
   events generated by writes to stderr. (#7903)

Improved Documentation
----------------------
 - twisted.logger's documentation is now correctly listed in the table
   of contents. (#7904)


Twisted Conch 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted Lore 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Mail 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Names 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted News 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Pair 15.2.1 (2015-05-23)
================================

No significant changes have been made for this release.


Twisted Runner 15.2.1 (2015-05-23)
==================================

No significant changes have been made for this release.


Twisted Web 15.2.1 (2015-05-23)
===============================

No significant changes have been made for this release.


Twisted Words 15.2.1 (2015-05-23)
=================================

No significant changes have been made for this release.


Twisted Core 15.2.0 (2015-05-18)
================================

Features
--------
 - twisted.internet.process has now been ported to Python 3. (#5987)
 - twisted.cred.credentials is now ported to Python 3. (#6176)
 - twisted.trial.unittest.TestCase's assertEqual, assertTrue, and
   assertFalse methods now pass through the standard library's more
   informative failure messages. (#6306)
 - The new package twisted.logger provides a new, fully tested, and
   feature-rich logging framework. The old module twisted.python.log
   is now implemented using the new framework. The new logger HOWTO
   documents the new framework. (#6750)
 - twisted.python.modules is now ported to Python 3. (#7804)
 - twisted.python.filepath.FilePath now supports Unicode (text) paths.
   Like the os module, instantiating it with a Unicode path will
   return a Unicode-mode FilePath, instantiating with a bytes path
   will return a bytes-mode FilePath. (#7805)
 - twisted.internet.kqreactor is now ported to Python 3 (#7823)
 - twisted.internet.endpoints.ProcessEndpoint is now ported to Python
   3. (#7824)
 - twisted.python.filepath.FilePath now has asBytesMode and asTextMode
   methods which return a FilePath in the requested mode. (#7830)
 - twisted.python.components.proxyForInterface now creates method
   proxies that can be used with functools.wraps. (#7832)
 - The tls optional dependency will now also install the idna package
   to validate idna2008 names. (#7853)

Bugfixes
--------
 - Don't raise an exception if `DefaultLogObserver.emit()` gets an
   event with a message that raises when `repr()` is called on it.
   Specifically: use `textFromEventDict()` instead of a separate (and
   inferior) message rendering implementation. (#6569)
 - twisted.cred.credentials.DigestedCredentials incorrectly handled
   md5-sess hashing according to the RFC, which has now been fixed.
   (#7835)
 - Fixed an issue with twisted.internet.task.LoopingCall.withCount
   where sometimes the passed callable would be invoked with "0" when
   we got close to tricky floating point boundary conditions. (#7836)
 - twisted.internet.defer now properly works with the new logging
   system. (#7851)
 - Change `messages` key to `log_io` for events generated by
   `LoggingFile`. (#7852)
 - twisted.logger had literal characters in docstrings that are now
   quoted. (#7854)
 - twisted.logger now correctly formats a log event with a key named
   `message` when passed to a legacy log observer. (#7855)
 - twisted.internet.endpoints.HostnameEndpoint now uses getaddrinfo
   properly on Python 3.4 and above. (#7886)

Improved Documentation
----------------------
 - Fix a typo in narrative documentation for logger (#7875)

Deprecations and Removals
-------------------------
 - tkunzip and tapconvert in twisted.scripts were deprecated in 11.0
   and 12.1 respectively, and are now removed. (#6747)
 - twisted.protocols.gps is deprecated in preference to
   twisted.positioning. (#6810)
 - twisted.scripts.tap2deb and twisted.scripts.tap2rpm are now
   deprecated. (#7682)
 - twisted.trial.reporter.TestResult and
   twisted.trial.reporter.Reporter contained deprecated methods (since
   8.0) which have now been removed. (#7815)

Other
-----
 - #6027, #7287, #7701, #7727, #7758, #7776, #7786, #7812, #7819,
   #7831, #7838, #7865, #7866, #7869, #7872, #7877, #7878, #7885


Twisted Conch 15.2.0 (2015-05-18)
=================================

Features
--------
 - twisted.conch.ssh.forwarding now supports local->remote forwarding
   of IPv6 (#7751)


Twisted Lore 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Mail 15.2.0 (2015-05-18)
================================

Features
--------
 - twisted.mail.smtp.sendmail now uses ESMTP. It will
   opportunistically enable encryption and allow the use of
   authentication. (#7257)


Twisted Names 15.2.0 (2015-05-18)
=================================

No significant changes have been made for this release.


Twisted News 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Pair 15.2.0 (2015-05-18)
================================

No significant changes have been made for this release.


Twisted Runner 15.2.0 (2015-05-18)
==================================

No significant changes have been made for this release.


Twisted Web 15.2.0 (2015-05-18)
===============================

Features
--------
 - twisted.web.static is now ported to Python 3. (#6177)
 - twisted.web.server.Site accepts requestFactory as constructor
   argument. (#7016)

Deprecations and Removals
-------------------------
 - twisted.web.util had some HTML generation functions deprecated
   since 12.1 that have now been removed. (#7828)

Other
-----
 - #6927, #7797, #7802, #7846


Twisted Words 15.2.0 (2015-05-18)
=================================

Bugfixes
--------
 - The resumeOffset argument to
   twisted.words.protocol.irc.DccFileReceive now works as it is
   documented. (#7775)


Twisted Core 15.1.0 (2015-04-02)
================================

Features
--------
 - Optional dependencies can be installed using the extra_requires
   facility provided by setuptools. (#3696)

Improved Documentation
----------------------
 - Twisted Trial's basics documentation now has a link to the
   documentation about how Trial finds tests. (#4526)

Deprecations and Removals
-------------------------
 - twisted.application.internet.UDPClient, deprecated since Twisted
   13.1.0, has been removed. (#7702)

Other
-----
 - #6988, #7005, #7006, #7007, #7008, #7044, #7335, #7666, #7723,
   #7724, #7725, #7748, #7763, #7765, #7766, #7768


Twisted Conch 15.1.0 (2015-04-02)
=================================

No significant changes have been made for this release.


Twisted Lore 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Mail 15.1.0 (2015-04-02)
================================

Bugfixes
--------
 - twisted.mail.smtp.ESMTPClient now does not fall back to plain SMTP
   if authentication or TLS is required and not able to occur. (#7258)

Other
-----
 - #6705


Twisted Names 15.1.0 (2015-04-02)
=================================

No significant changes have been made for this release.

Other
-----
 - #7728


Twisted News 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Pair 15.1.0 (2015-04-02)
================================

No significant changes have been made for this release.


Twisted Runner 15.1.0 (2015-04-02)
==================================

No significant changes have been made for this release.

Other
-----
 - #7726


Twisted Web 15.1.0 (2015-04-02)
===============================

Features
--------
 - twisted.web.static.File allows defining a custom resource for
   rendering forbidden pages. (#6951)

Other
-----
 - #7000, #7485, #7750, #7762


Twisted Words 15.1.0 (2015-04-02)
=================================

Deprecations and Removals
-------------------------
 - twisted.words.protocols.msn is now deprecated (#6395)

Other
-----
 - #6494


Twisted Core 15.0.0 (2015-01-24)
================================

Features
--------
 - twisted.internet.protocol.ClientFactory (and subclasses) may now
   return None from buildProtocol to immediately close the connection.
   (#710)
 - twisted.trial.unittest.SynchronousTestCase.assertRaises can now
   return a context manager. (#5339)
 - Implementations of
   twisted.internet.interfaces.IStreamClientEndpoint included in
   Twisted itself will now handle None being returned from the client
   factory's buildProtocol method by immediately closing the
   connection and firing the waiting Deferred with a Failure. (#6976)
 - inlineCallbacks now supports using the return statement with a
   value on Python 3 (#7624)
 - twisted.spread.banana.Banana.sendEncoded() now raises a more
   informative error message if the user tries to encode objects of
   unsupported type. (#7663)

Bugfixes
--------
 - twisted.internet.interfaces.IReactorMulticast.listenMultiple works
   again RHEL 6's python 2.6. (#7159)
 - Allow much more of the code within Twisted to use ProcessEndpoint
   by adding IPushProducer and IConsumer interfaces to its resulting
   transport. (#7436)
 - twisted.internet.ssl.Certificate(...).getPublicKey().keyHash() now
   produces a stable value regardless of OpenSSL version.
   Unfortunately this means that it is different than the value
   produced by older Twisted versions. (#7651)
 - twisted.python.reflect.safe_str on Python 3 converts utf-8 encoded
   bytes to clean str instead of "b'a'" (#7660)
 - twisted.spread.banana.Banana now raises NotImplementedError when
   receiving pb messages without pb being the selected dialect (#7662)
 - The SSL server string endpoint parser
   (twisted.internet.endpoints.serverFromString) now constructs
   endpoints which, by default, disable the insecure SSLv3 protocol.
   (#7684)
 - The SSL client string endpoint parser
   (twisted.internet.endpoints.clientFromString) now constructs
   endpoints which, by default, disable the insecure SSLv3 protocol.
   (#7686)

Improved Documentation
----------------------
 - inlineCallbacks now has introductory documentation. (#1009)
 - The echoclient example now uses twisted.internet.task.react.
   (#7083)
 - Twisted Trial's how-to documentation now has a link to Twisted's
   contribution guidelines and has been reformatted. (#7475)
 - Fixed a path error in the make.bat file for building Sphinx
   documentation, so that it is now possible to build the documentation
   using make.bat on Windows. (#7542)

Deprecations and Removals
-------------------------
 - twisted.python.filepath.FilePath.statinfo was deprecated. (#4450)
 - twisted.internet.defer.deferredGenerator is now deprecated.
   twisted.internet.defer.inlineCallbacks should be used instead.
   (#6044)
 - Pickling twisted.internet.ssl.OptionSSLCertificationOptions and
   twisted.internet.ssl.Keypair is no longer supported. __getstate__
   and __setstate__ methods of these classes have been deprecated.
   (#6166)
 - twisted.spread.jelly's support for unjellying "instance" atoms is
   now deprecated. (#7653)

Other
-----
 - #3404, #4711, #5730, #6042, #6626, #6947, #6953, #6989, #7032,
   #7038, #7039, #7097, #7098, #7142, #7143, #7154, #7155, #7156,
   #7157, #7158, #7160, #7161, #7162, #7164, #7165, #7176, #7234,
   #7252, #7329, #7333, #7355, #7369, #7370, #7419, #7529, #7531,
   #7534, #7537, #7538, #7620, #7621, #7633, #7636, #7637, #7638,
   #7640, #7641, #7642, #7643, #7665, #7667, #7713, #7719


Twisted Conch 15.0.0 (2015-01-24)
=================================

Features
--------
 - The new APIs: twisted.conch.checkers.IAuthorizedKeysDB,
   twisted.conch.checkers.InMemorySSHKeyDB,
   twisted.conch.checkers.UNIXAuthorizedKeyFiles, and
   twisted.conch.checkers.SSHPublicKeyChecker have been added to
   provide functionality to check the validity of SSH public keys and
   specify where authorized keys are to be found. (#7144)

Deprecations and Removals
-------------------------
 - twisted.conch.checkers.SSHPublicKeyDatabase is now deprecated in
   favor of a twisted.conch.checkers.SSHPublicKeyChecker instantiated
   with a twisted.conch.checkers.UNIXAuthorizedKeyFiles. (#7144)

Other
-----
 - #6626, #7002, #7526, #7532, #7698


Twisted Lore 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.


Twisted Mail 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #6999, #7708


Twisted Names 15.0.0 (2015-01-24)
=================================

Bugfixes
--------
 - twisted.names.secondary.SecondaryAuthority can now answer queries
   again (broken since 13.2.0). (#7408)

Other
-----
 - #7352


Twisted News 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #7703


Twisted Pair 15.0.0 (2015-01-24)
================================

No significant changes have been made for this release.

Other
-----
 - #7722


Twisted Runner 15.0.0 (2015-01-24)
==================================

No significant changes have been made for this release.


Twisted Web 15.0.0 (2015-01-24)
===============================

Features
--------
 - twisted.web.client.Agent.usingEndpointFactory allows creating an
   Agent that connects in non-standard ways, e.g. via a proxy or a
   UNIX socket. (#6634)
 - The Deferred returned by twisted.web.client.readBody can now be
   cancelled. (#6686)

Deprecations and Removals
-------------------------
 - twisted.web.iweb.IRequest.getClient is now deprecated.  Its
   implementation in Twisted, twisted.web.http.Request.getClient, is
   also deprecated and will no longer attempt to resolve the client IP
   address to a hostname. (#2252)

Other
-----
 - #7247, #7302, #7680, #7689


Twisted Words 15.0.0 (2015-01-24)
=================================

No significant changes have been made for this release.

Other
-----
 - #6994, #7163, #7622
