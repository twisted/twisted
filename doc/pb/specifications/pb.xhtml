<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>NewPB</title>
<link href="stylesheet-unprocessed.css" type="text/css" rel="style" />
</head>

<body>
<h1>NewPB</h1>

<p>This document describes the new PB protocol. This is a layer on top of <a
href="banana.xhtml">Banana</a> which provides remote object access (method
invocation and instance transfer).</p>

<p>Fundamentally, PB is about one side keeping a
<code>RemoteReference</code> to the other side's <q>Referenceable</q>. The
Referenceable has some methods that can be invoked remotely: functionality
it is offering to remote callers. Those callers hold RemoteReferences which
point to it. The RemoteReference object offers a way to invoke those methods
(generally through the <code>callRemote</code> method).</p>

<p>There are plenty of other details, starting with how the RemoteReference
is obtained, and how arguments and return values are communicated.</p>

<p>For the purposes of this document, we will designate the side that holds
the actual <code>Referenceable</code> object as <q>local</q>, and the side
that holds the proxy <code>RemoteReference</code> object as <q>remote</q>.
This distinction is only meaningful with respect to a single
RemoteReference/Referenceable pair. One program may hold Referenceable
<q>A</q> and RemoteReference <q>B</q>, paired with another that holds
RemoteReference <q>A</q> and Referenceable <q>B</q>. Once initialization is
complete, PB is a symmetric protocol.</p>

<p>It is helpful to think of PB as providing a wire or pipe that connects
two programs. Objects are put into this pipe at one end, and something
related to the object comes out the other end. These two objects are said to
correspond to each other. Basic types (like lists and dictionaries) are
handled by Banana, but more complex types (like instances) are treated
specially, so that most of the time there is a <q>native</q> form (as
present on the local side) that goes into the pipe, and a remote form that
comes out.</p>

<h2>Initialization</h2>

<p>The PB session begins with some feature negotiation and (generally) the
receipt of a VocabularyDict. Usually this takes place over an interactive
transport, like a TCP connection, but newpb can also be used in a more
batched message-oriented mode, as long as both the creator of the method
call request and its eventual consumer are in agreement about their shared
state (at least, this is the intention.. there are still pieces that need to
be implemented to make this possible).</p>

<p>The local side keeps a table which provides a bidirectional mapping
between <code>Referenceable</code> objects and a connection-local
<q>object-ID</q> number. This table begins with a single object called the
<q>Root</q>, which is implicitly given ID number 0. Everything else is
bootstrapped through this object. For the typical PB Broker, this root
object performs cred authentication and returns other Referenceables as the
cred Avatar.</p>

<p>The remote side has a collection of <code>RemoteReference</code> objects,
each of which knows the object-ID of the corresponding Referenceable, as
well as the Broker which provides the connection to the other Broker. The
remote side must do reference-tracking of these RemoteReferences, because as
long as it remains alive, the local-side Broker must maintain a reference to
the original Referenceable.</p>

<h2>Method Calls</h2>

<p>The remote side invokes a remote method by calling
<code>ref.callRemote()</code> on its RemoteReference. This starts by
validating the method name and arguments against a <q>Schema</q> (described
below). It then creates a new Request object which will live until the method
call has either completed successfully or failed due to an exception
(including the connection being lost). <code>callRemote</code> returns a
Deferred, which does not fire until the request is finished.</p>

<p>It then sends a <code>call</code> banana sequence over the wire. This
sequence indicates the request ID (used to match the request with the
resulting <code>answer</code> or <code>error</code> response), the object ID
of the Referenceable being targeted, a string to indicate the name of the
method being invoked, and the arguments to be passed into the method.</p>

<p>All arguments are passed by name (i.e. keyword arguments instead of
positional parameters). Each argument is subject to the <q>argument
transformation</q> described below.</p>

<p>The local side receives the <code>call</code> sequence, uses the object-ID
to look up the Referenceable, finds the desired method, then applies the
method's schema to the incoming arguments. If they are acceptable, it invokes
the method. A normal return value it sent back immediately in an
<code>answer</code> sequence (subject to the same transformation as the
inbound arguments). If the method returns a Deferred, the answer will be sent
back when the Deferred fires. If the method raises an exception (or the
Deferred does an errback), the resulting Failure is sent back in a
<code>error</code> sequence. Both the <code>answer</code> and the
<code>error</code> start with the request-ID so they can be used to complete
the Request object waiting on the remote side.</p>

<p>The original Deferred (the one produced by <code>callRemote</code>) is
finally callbacked with the results of the method (or errbacked with a
Failure or RemoteFailure object).</p>


<h3>Example</h3>

<p>This code runs on the <q>local</q> side: the one with the
<code>pb.Referenceable</code> which will respond to a remote invocation. </p>

<pre class="python">
class Responder(pb.Referenceable):
    def remote_add(self, a, b):
        return a+b
</pre>

<p>and the following code runs on the <q>remote</q> side (the one which holds
a <code>pb.RemoteReference</code>):</p>

<pre class="python">
def gotAnswer(results):
    print results

d = rr.callRemote("add", a=1, b=2)
d.addCallback(gotAnswer)
</pre>

<p>Note that the arguments are passed as named parameters: oldpb used both
positional parameters and named (keyword) arguments, but newpb prefers just
the keyword arguments. TODO: newpb will probably convert positional
parameters to keyword arguments (based upon the schema) before sending them
to the remote side.</p>


<h3>Using RemoteInterfaces</h3>

<p>To nail down the types being sent across the wire, you can use a
<code>RemoteInterface</code> to define the methods that are implemented by
any particular <code>pb.Referenceable</code>:</p>

<pre class="python">
class RIAdding(pb.RemoteInterface):
    def add(a=int, b=int): return int

class Responder(pb.Referenceable):
    implements(RIAdding)
    def remote_add(self, a, b):
        return a+b

# and on the remote side:
d = rr.callRemote(RIAdding['add'], a=1, b=2)
d.addCallback(gotAnswer)
</pre>

<p>In this example, the <q>RIAdding</q> remote interface defines a single
method <q>add</q>, which accepts two integer parameters and returns an
integer. This method (technically a classmethod) is used instead of the
string form of the method name. What does this get us?</p>

<ul>
  <li>The calling side will pre-check its arguments against the constraints
  that it believes to be imposed by the remote side. It will raise a
  Violation rather than send parameters that it thinks will be rejected.</li>

  <li>The receiving side will enforce the constraints, causing the method
  call to errback (with a Violation) if they are not met. This means the code
  in <code>remote_add</code> does not need to worry about what strange types
  it might be given, such as two strings, or two lists.</li>

  <li>The receiving side will pre-check its return argument before sending it
  back. If the method returns a string, it will cause a Violation exception
  to be raised. The caller will get this Violation as an errback instead of
  whatever (illegal) value the remote method computed.</li>

  <li>The sending side will enforce the return-value constraint (raising a
  Violation if it is not met). This means the calling side (in this case the
  <code>gotAnswer</code> callback function) does not need to worry about what
  strange type the remote method returns.</li>
</ul>

<p>You can use either technique: with RemoteInterfaces or without. To get the
type-checking benefits, you must use them. If you do not, PB cannot protect
you against memory consumption attacks.</p>


<h3>RemoteInterfaces</h3>

<p>RemoteInterfaces are passed by name. Each side of a PB connection has a
table which maps names to RemoteInterfaces (subclasses of
<code>pb.RemoteInterface</code>). Metaclass magic is used to add an entry to
this table each time you define a RemoteInterface subclass, using the
<code>__remote_name__</code> attribute (or reflect.qual() if that is not
set).</p>

<p>Each <code>Referenceable</code> that goes over the wire is accompanied by
the list of RemoteInterfaces which it claims to implement. On the receiving
side, these RemoteInterface names are looked up in the table and mapped to
actual (local) RemoteInterface classes.</p>

<p>TODO: it might be interesting to serialize the RemoteInterface class and
ship it over the wire, rather than assuming both sides have a copy (and that
they agree). However, if one side does not have a copy, it is unlikely that
it will be able to do anything very meaningful with the remote end.</p>

<p>The syntax of RemoteInterface is still in flux. The basic idea is that
each method of the RemoteInterface defines a remotely invokable method,
something that will exist with a <q>remote_</q> prefix on any
<code>pb.Referenceable</code>s which claim to implement it.</p>

<p>Those methods are defined with a number of named parameters. The default
value of each parameter is something which can be turned into a
<code>Constraint</code> according to the rules of schema.makeConstraint .
This means you can use things like <code>(int, str, str)</code> to mean a
tuple of exactly those three types.</p>

<p>Note that the methods of the RemoteInterface do <em>not</em> list
<q>self</q> as a parameter. As the zope.interface documentation points out,
<q>self</q> is an implemenation detail, and does not belong in the interface
specification. Another way to think about it is that, when you write the code
which calls a method in this interface, you don't include <q>self</q> in the
arguments you provide, therefore it should not appear in the public
documentation of those methods.</p>

<p>The method is required to return a value which can be handled by
schema.makeConstraint: this constraint is then applied to the return value of
the remote method.</p>

<p>Other attributes of the method (perhaps added by decorators of some sort)
will, some day, be able to specify specialized behavior of the method. The
brainstorming sessions have come up with the following ideas:</p>

<ul>
  <li>.wait=False: don't wait for an answer</li>
  <li>.reliable=False: feel free to send this over UDP</li>
  <li>.ordered=True: but enforce order between successive remote calls</li>
  <li>.priority=3: use priority queue / stream #3</li>
  <li>.failure=Full: allow/expect full Failure contents (stack frames)</li>
  <li>.failure=ErrorMessage: only allow/expect truncated CopiedFailures</li>
</ul>

<p>We are also considering how to merge the RemoteInterface with other useful
interface specifications, in particular zope.interface and
formless.TypedInterface .</p>


<h2>Argument Transformation</h2>

<p>To understand this section, it may be useful to review the <a
href="banana.xhtml">Banana</a> documentation on serializing object graphs.
Also note that method arguments and method return values are handled
identically.</p>

<p>Basic types (lists, tuples, dictionaries) are serialized and unserialized
as you would expect: the resulting object would (if it existed in the
sender's address space) compare as equal (but of course not
<q>identical</q>, because the objects will exist at different memory
locations).</p>

<h3>Shared References, Serialization Scope</h3>

<p>Shared references to the same object are handled correctly. Banana is
responsible for noticing that a sharable object has been serialized before
(or at least has begun serialization) and inserts reference markers so that
the object graph can be reconstructed. This introduces the concept of
serialization scope: the boundaries beyond which shared references are not
maintained.</p>

<p>For PB, serialization is scoped to the method call. If an object is
referenced by two arguments to the same method call, that method will see
two references to the same object. If those arguments are containers of some
form, which (eventually) hold a reference to the same object, the object
graph will be preserved. For example:</p>

<pre class="python">
class Caller:
    def start(self):
        obj = [1, 2, 3]
        self.remote.callRemote("both", obj, obj)
        self.remote.callRemote("deeper", ["a", obj], (4, 5, obj))

class Called(pb.Referenceable):
    def remote_both(self, arg1, arg2):
        assert arg1 is arg2
        assert arg1 == [1,2,3]
    def remote_deeper(self, listarg, tuplearg):
        ref1 = listarg[1]
        ref2 = tuplearg[2]
        assert ref1 is ref2
        assert ref1 == [1,2,3]
</pre>

<p>But if the remote-side object is referenced in two distinct remote method
invocations, the local-side methods will see two separate objects. For
example:</p>

<pre class="python">
class Caller:
    def start(self):
        self.obj = [1, 2, 3]
        d = self.remote.callRemote("one", self.obj)
        d.addCallback(self.next)
    def next(self, res):
        self.remote.callRemote("two", self.obj)

class Called(pb.Referenceable):
    def remote_one(self, ref1):
        assert ref1 == [1,2,3]
        self.ref1 = ref1

    def remote_two(self, ref2):
        assert ref2 == [1,2,3]
        assert ref1 is not ref2 # not the same object
</pre>

<p>You can think of the method call itself being a node in the object graph,
with the method arguments as its children. The method call node is picked up
and the resulting sub-tree is serialized with no knowledge of anything
outside the sub-tree<span class="footnote">This isn't quite true: for some
objects, serialization is scoped to the connection as a whole.
Referenceables and RemoteReferences are like this.</span>.</p>

<p>The value returned by a method call is serialized by itself, without
reference to the arguments that were given to the method. If a remote method
is called with a list, and the method returns its argument unchanged, the
caller will get back a deep copy of the list it passed in.</p>

<h3>Referenceables, RemoteReferences</h3>

<p>Referenceables are transformed into RemoteReferences when they are sent
over the wire. As one side traverses the object graph of the method arguments
(or the return value), each <code>Referenceable</code> object it encounters
it serialized with a <code>my-reference</code> sequence, that includes the
object-ID number. When the other side is unserializing the token stream, it
creates a <code>RemoteReference</code> object, or uses one that already
exists.</p>

<p>Likewise, if an argument (or return value) contains a
<code>RemoteReference</code>, and it is being sent back to the Broker that
holds the original <code>Referenceable</code> then it will be turned back
into that Referenceable when it arrives. In this case, the caller of a
remote method which returns its argument unchanged <em>will</em> see a a
result that is identical to what it passed in:</p>

<pre class="python">
class Target(pb.Referenceable):
    pass

class Caller:
    def start(self):
        self.obj = Target()
        d = self.remote.callRemote("echo", self.obj)
        d.addCallback(self.next)
    def next(self, res):
        assert res is self.obj

class Called(pb.Referenceable):
    def remote_echo(self, arg):
        # arg is a RemoteReference to a Target() instance 
        return arg
</pre>

<p>These references have a serialization scope which extends across the
entire connection. As long as two method calls share the same
<code>Broker</code> instance (which generally means they share the same TCP
socket), they will both serialize <code>Referenceable</code>s into identical
<code>RemoteReference</code>s. This also means that both sides do
reference-counting to insure that the Referenceable doesn't get
garbage-collected while a remote system holds a RemoteReference that points
to it.</p>

<p>In the future, there may be other classes which behave this way. In
particular, <q>Referenceable</q> and <q>Callable</q> may be distinct
qualities.</p>


<h3>Copyable, RemoteCopy</h3>

<p>Some objects can be marked to indicate that they should be copied bodily
each time they traverse the wire (pass-by-value instead of
pass-by-reference). Classes which inherit from <code>pb.Copyable</code> are
passed by value. Their <code>getTypeToCopy</code> and
<code>getStateToCopy</code> methods are used to assemble the data that will
be serialized. These methods default to plain old <code>reflect.qual</code>
(which provides the fully-qualified name of the class) and the instance's
attribute <code>__dict__</code>. You can override these to provide a
different (or smaller) set of state attributes to the remote end.</p>


<pre class="python">
class Source(pb.Copyable):
    def getStateToCopy(self):
        state = self.__dict__.copy()
        del state['private']
        state['children'] = []
        return state
</pre>

<p>Rather than subclass <code>pb.Copyable</code>, you can also implement the
<code>flavors.ICopyable</code> interface:</p>

<pre class="python">
from twisted.python import reflect

class Source2:
    implements(flavors.ICopyable)
    def getTypeToCopy(self):
        return reflect.qual(self.__class__)
    def getStateToCopy(self):
        return self.__dict__
</pre>

<p>.. or register an ICopyable adapter. Using the adapter allows you to
define serialization behavior for third-party classes that are out of your
control (ones which you cannot rewrite to inherit from
<code>pb.Copyable</code>).</p>

<pre class="python">
class Source3:
    pass

class Source3Copier:
    implements(flavors.ICopyable)

    def getTypeToCopy(self):
        return 'foo.Source3'
    def getStateToCopy(self):
        orig = self.original
        d = { 'foo': orig.foo, 'bar': orig.bar }
        return d

registerAdapter(Source3Copier, Source3, flavors.ICopyable)
</pre>


<p>On the other end of the wire, the receiving side must register a
<code>RemoteCopy</code> subclass under the same name as returned by the
sender's <code>getTypeToCopy</code> value. This subclass is used as a factory
to create instances that correspond to the original <code>Copyable</code>.
The registration can either take place explicitly (with
<code>pb.registerRemoteCopy</code>), or automatically (by setting the
<code>copytype</code> attribute in the class definition).</p>

<p>The default <code>RemoteCopy</code> behavior simply sets the instance's
<code>__dict__</code> to the incoming state, which may be plenty if you are
willing to let outsiders arbitrarily manipulate your object state. If so, and
you believe both peers are importing the same source file, it is enough to
create and register the <code>RemoteCopy</code> at the same time you create
the <code>Copyable</code>:</p>

<pre class="python">
class Source(pb.Copyable):
    def getStateToCopy(self):
        state = self.__dict__.copy()
        del state['private']
        state['children'] = []
        return state
class Remote(pb.RemoteCopy):
    copytype = reflect.qual(Source)
</pre>

<p>You can do something special with the incoming object state by overriding
the <code>setCopyableState</code> method. This may allow you to do some
sanity-checking on the state before trusting it.</p>

<pre class="python">
class Remote(pb.RemoteCopy):
    def setCopyableState(self, state):
        state['count'] = 0
        self.__dict__ = state
        self.total = self.one + self.two

# show explicit registration, instead of using 'copytype' class attribute
pb.registerRemoteCopy(reflect.qual(Source), Remote)
</pre>

<p>You can also set a <a href="schema.xhtml">constraint</a> on the inbound
object state, which provides a way to enforce some type checking on the state
components as they arrive. This protects against resource-consumption attacks
where someone sends you a zillion-byte string as part of the object's
state.</p>

<pre class="python">
class Remote(pb.RemoteCopy):
    stateSchema = schema.AttributeDictConstraint(('foo', int),
                                                 ('bar', str))
</pre>

<p>In this example, the object will only accept two attributes: <q>foo</q>
(which must be a number), and <q>bar</q> (which must be a string shorter than
the default limit of 1000 characters). Various classes from the
<code>schema</code> module can be used to construct more complicated
constraints.</p>



<h3>Slicers, ISlicer</h3>

<p>Each object gets <q>Sliced</q> into a stream of tokens as they go over the
wire: Referenceable and Copyable are merely special cases. These classes have
Slicers which implement specific behaviors when the serialization process is
asked to send their instances to the remote side. You can implement your own
Slicers to take complete control over the serialization process. The most
useful reason to take advantage of this feature is to implement <q>streaming
slicers</q>, which can minimize in-memory buffering by only producing Banana
tokens on demand as space opens up in the transport.</p>

<p>Banana Slicers are documented in detail in the <a
href="banana.xhtml">Banana</a> documentation. Once you create a Slicer class,
you will want to <q>register</q> it, letting Banana know that this Slicer is
useful for conveying certain types of objects across the wire. The registry
maps a type to a Slicer class (which is really a slicer factory), and is
implemented by registering the slicer as a regular <q>adapter</q> for the
<code>ISlicer</code> interface. For example, lists are serialized by the
<code>ListSlicer</code> class, so <code>ListSlicer</code> is registered as
the slicer for the <code>list</code> type:</p>

<pre class="python">
class ListSlicer(BaseSlicer):
    opentype = ("list",)
    slices = list
</pre>

<p>Slicer registration can be either explicit or implicit. In this example,
an implicit registration is used: by setting the <q>slices</q> attribute to
the <code>list</code> type, the BaseSlicer's metaclass automatically
registers the mapping from <code>list</code> to ListSlicer.</p>

<p>To explicitly register a slicer, just leave <code>opentype</code> set to
None (to disable auto-registration), and then register the slicer
manually.</p>

<pre class="python">
class TupleSlicer(BaseSlicer):
    opentype = ("tuple",)
    slices = None
    ...
registerAdapter(TupleSlicer, tuple, pb.ISlicer)
</pre>

<p>As with ICopyable, registering an ISlicer adapter allows you to define
exactly how you wish to serialize third-party classes which you do not get to
modify.</p>


<h3>Unslicers</h3>

<p>On the other side of the wire, the incoming token stream is handed to an
<code>Unslicer</code>, which is responsible for turning the set of tokens
into a single finished object. They are also responsible for enforcing limits
on the types and sizes of the tokens that make up the stream. Unslicers are
also described in greater detail in the <a href="banana.xhtml">Banana</a>
docs.</p>

<p>As with Slicers, Unslicers need to be registered to be useful. This
registry maps <q>opentypes</q> to Unslicer classes (i.e. factories which can
produce an unslicer instance each time the given opentype appears in the
token stream). Therefore it maps tuples to subclasses of
<code>BaseUnslicer</code>.</p>

<p>Again, this registry can be either implicit or explicit. If the Unslicer
has a non-None class attribute named <code>opentype</code>, then it is
automatically registered. If it does not have this attribute (or if it is set
to None), then no registration is performed, and the Unslicer must be
manually registered:</p>

<pre class="python">
class MyUnslicer(BaseUnslicer):
    ...

pb.registerUnslicer(('myopentype',), MyUnslicer)
</pre>

<p>Also remember that this registry is global, and that you cannot register
two Unslicers for the same opentype (you'll get an exception at
class-definition time, which will probably result in an ImportError).</p>


<h3>Slicer/Unslicer Example</h3>

<p>The simplest kind of slicer has a <code>sliceBody</code> method (a
generator) which yields a series of tokens. To demonstrate how to build a
useful Slicer, we'll write one that can send large strings across the wire in
pieces. Banana can send arbitrarily long strings in a single token, but each
token must be handed to the transport layer in an indivisble chunk, and
anything that doesn't fit in the transmit buffers will be stored in RAM until
some space frees up in the socket. Practically speaking, this means that
anything larger than maybe 50kb will spend a lot of time in memory,
increasing the RAM footprint for no good reason.</p>

<p>Because of this, it is useful to be able to send large amounts of data in
smaller pieces, and let the remote end reassemble them. The following Slicer
is registered to handle all open files (perhaps not the best idea), and
simply emits the contents in 10kb chunks.</p>

<p>(readers familiar with oldpb will notice that this Slicer/Unslicer pair
provide similar functionality to the old FilePager class. The biggest
improvement is that newpb can accomplish this without the extra round-trip
per chunk. The downside is that, unless you enable streaming in your Broker,
no other methods can be invoked while the file is being transmitted. The
upside of the downside is that this lets you retain in-order execution of
remote methods, and that you don't have to worry changes to the contents of
the file causing corrupt data to be sent over the wire. The oter upside of
the downside is that, if you enable streaming, you can do whatever other
processing you wish between data chunks.)</p>

<pre class="python">
class BigFileSlicer(BaseSlicer):
    opentype = ("bigfile",)
    slices = types.FileType
    CHUNKSIZE = 10000

    def sliceBody(self, streamable, banana):
        while 1:
            chunk = self.obj.read(self.CHUNKSIZE)
            if not chunk:
                return
            yield chunk
</pre>

<p>To receive this, you would use the following minimal Unslicer at the other
end. Note that this Unslicer does not do as much as it could in the way of
constraint enforcement: an attacker could easily make you consume as much
memory as they wished by simply sending you a never-ending series of
chunks.</p>

<pre class="python">
class BigFileUnslicer(LeafUnslicer):
    opentype = ("bigfile",)

    def __init__(self):
        self.chunks = []

    def checkToken(self, typebyte, size):
        if typebyte != tokens.STRING:
            raise BananaError("BigFileUnslicer only accepts strings")

    def receiveChild(self, obj):
        self.chunks.append(obj)

    def receiveClose(self):
        return "".join(self.chunks)
</pre>

<p>The <code>opentype</code> attribute causes this Unslicer to be implicitly
registered to handle any incoming sequences with an <q>index tuple</q> of
<code>("bigfile",)</code>, so each time BigFileSlicer is used, a
BigFileUnslicer will be created to handle the results.</p>

<p>A more complete example would want to write the file chunks to disk at
they arrived, or process them incrementally. It might also want to have some
way to limit the overall size of the file, perhaps by having the first chunk
be an integer with the promised file size. In this case, the example might
look like this somewhat contrived (and somewhat insecure) Unslicer:</p>

<pre class="python">
class SomewhatLargeFileUnslicer(LeafUnslicer):
    opentype = ("bigfile",)

    def __init__(self):
        self.fileSize = None
        self.size = 0
        self.output = open("/tmp/bigfile.txt", "w")

    def checkToken(self, typebyte, size):
        if self.fileSize is None:
            if typebyte != tokens.INT:
                raise BananaError("fileSize must be an INT")
        else:
            if typebyte != tokens.STRING:
                raise BananaError("BigFileUnslicer only accepts strings")
            if self.size + size > self.fileSize:
                raise BananaError("size limit exceeded")

    def receiveChild(self, obj):
        if self.fileSize is None:
            self.fileSize = obj
            # decide if self.fileSize is too big, raise error to refuse it
        else:
            self.output.write(obj)
            self.size += len(obj)

    def receiveClose(self):
        self.output.close()
        return open("/tmp/bigfile.txt", "r")
</pre>

<p>This constrained BigFileUnslicer uses the fact that each STRING token
comes with a size, which can be used to enforce the promised filesize that
was provided in the first token. The data is streamed to a disk file as it
arrives, so no more than CHUNKSIZE of memory is required at any given
time.</p>


<h3>Streaming Slicers</h3>

<p>TODO: add example</p>

<p>The following slicer will, when the broker allows streaming, will yield
the CPU to other reactor events that want processing time. (This technique
becomes somewhat inefficient if there is nothing else contending for CPU
time, and if this matters you might want to use something which sends N
chunks before yielding, or yields only when some other known service
announces that it wants CPU time, etc).</p>

<pre class="python">
class BigFileSlicer(BaseSlicer):
    opentype = ("bigfile",)
    slices = types.FileType
    CHUNKSIZE = 10000

    def sliceBody(self, streamable, banana):
        while 1:
            chunk = self.obj.read(self.CHUNKSIZE)
            if not chunk:
                return
            yield chunk
            if streamable:
                d = defer.Deferred()
                reactor.callLater(0, d.callback, None)
                yield d
</pre>

<p>The next example will deliver data as it becomes available from a
hypothetical slow process.</p>

<pre class="python">
class OutputSlicer(BaseSlicer):
    opentype = ("output",)

    def sliceBody(self, streamable, banana):
        assert streamable # requires it
        while 1:
            if self.process.finished():
                return
            chunk = self.process.read(self.CHUNKSIZE)
            if not chunk:
                d = self.process.waitUntilDataIsReady()
                yield d
            else:
                yield chunk
</pre>

<p>Streamability is required in this example because otherwise the Slicer is
required to provide chunks non-stop until the object has been completely
serialized. If the process cannot deliver data, it's not like the Slicer can
block waiting until it becomes ready. Prohibiting streamability is done to
ensure coherency of serialized state, and the only way to guarantee this is
to not let any non-Banana methods get CPU time until the object has been
fully processed.</p>

<h3>Streaming Unslicers</h3>

<p>On the receiving side, the Unslicer can be made streamable too. This is
considerably easier than on the sending side, because there are fewer
concerns about state coherency.</p>

<p>A streaming Unslicer is merely one that delivers some data directly from
the <code>receiveChild</code> method, rather than accumulating it until the
<code>receiveClose</code> method. The SomewhatLargeFileUnslicer example from
above is actually a streaming Unslicer. Nothing special needs to be
done.</p>

<p>On the other hand, it can be tricky to know where exactly to deliver the
data being streamed. The streamed object is probably part of a larger
structure (like a method call), where the higher-level attribute can be used
to determine which object or method should be called with the incoming data
as it arrives. The current Banana model is that each completed object (as
returned by the child's <code>receiveClose</code> method) is handed to the
parent's <code>receiveChild</code> method. The parent can do whatever it
wants with the results. To make streaming Unslicers more useful, the parent
should be able to set up a target for the data at the time the child
Unslicer is created.</p>

<p>More work is needed in this area to figure out how this functionality
should be exposed.</p>


<h3>Arbitrary Instances are NOT serialized</h3>

<p>Arbitrary instances (that is, anything which does not have an
<code>ISlicer</code> adapter) are <em>not</em> serialized. If an argument to
a remote method contains one, you will get a Violation exception when you
attempt to serialize it (i.e., the Deferred that you get from
<code>callRemote</code> will errback with a Failure that contains a
Violation exception). If the return value contains one, the Violation will
be logged on the local side, and the remote caller will see an error just as
if your method had raised a Violation itself.</p>

<p>There are two reasons for this. The first is a security precaution: you
must explicitly mark the classes that are willing to reveal their contents
to the world. This reduces the chance of leaking sensitive information.</p>

<p>The second is because it is not actually meaningful to send the contents
of an arbitrary object. The recipient only gets the class name and a
dictionary with the object's state. Which class should it use to create the
corresponding object? It could attempt to import one based upon the
classname (the approach pickle uses), but that would give a remote attacker
unrestricted access to classes which could do absolutely anything: very
dangerous.</p>

<p>Both ends must be willing to transport the object. The sending side
expresses this by marking the class (subclassing Copyable, or registering an
ISlicer adapter). The receiving side must register the class as well, by
doing registerUnslicer or using the <code>opentype</code> attribute in a
suitable Unslicer subclass definition.</p>


<h2>PB Sequences</h2>

<p>There are several Banana sequences which are used to support the RPC
mechanisms of Perspective Broker. These are in addition to the usual ones
listed in the Banana <a href="banana.xhtml">docs</a>.</p>

<h3>Top-Level Sequences</h3>

<p>These sequences only appear at the top-level (never inside another
object).</p>

<table border="" width="">
  <tr><td colspan="2">PB (method call) Sequences</td></tr>

  <tr><td>method call (<code>callRemote</code>)</td>
      <td>OPEN(call) INT(request-id) INT/STR(your-reference-id)
        STRING(interfacename) STRING(methodname)
        (STRING(argname),argvalue)..
        CLOSE</td></tr>

  <tr><td>method response (success)</td>
      <td>OPEN(answer) INT(request-id) value CLOSE</td></tr>
  <tr><td>method response (exception)</td>
      <td>OPEN(error) INT(request-id) value CLOSE</td></tr>

  <tr><td>RemoteReference.__del__</td>
      <td>OPEN(decref) INT(your-reference-id) CLOSE</td></tr>
  
</table>

<h3>Internal Sequences</h3>

<p>The following sequences are used to serialize PB-specific objects. They
never appear at the top-level, but only as the argument value or return
value (or somewhere inside them).</p>

<table border="" width="">
  <tr><td colspan="2">PB (method call) Sequences</td></tr>

  <tr><td>pb.Referenceable</td>
      <td>OPEN(my-reference) INT(clid)
        [OPEN(list) InterfaceList.. CLOSE]
        CLOSE</td></tr>

  <tr><td>pb.RemoteReference</td>
      <td>OPEN(your-reference) INT/STR(clid)
        CLOSE</td></tr>

  <tr><td>pb.Copyable</td><td>OPEN(copyable) STRING(reflect.qual(class))
  (attr,value).. CLOSE</td></tr>

</table>

<p>The first time a <code>pb.Referenceable</code> is sent, the second object
is an InterfaceList, which is a list of interfacename strings, and therefore
constrainable by a schema of ListOf(str) with some appropriate
maximum-length restrictions. This InterfaceList describes all the Interfaces
that the corresponding <code>pb.Referenceable</code> implements. The
receiver uses this list to look up local Interfaces (and therefore Schemas)
to attach to the <code>pb.RemoteReference</code>. This is how method schemas
are checked on the sender side.</p>

<p>This implies that Interfaces must be registered, just as classes are for
<code>pb.Copyable</code>. TODO: what happens if an unknown Interface is
received?</p>

<p>Classes which wish to be passed by value should either inherit from
<code>pb.Copyable</code> or have an <code>ICopyable</code> adapter
registered for them. On the receiving side, the
<code>registerRemoteCopy</code> function must be used to register a factory,
which can be a <code>pb.RemoteCopy</code> subclass or something else which
implements <code>IRemoteCopy</code>.</p>

<p><code>Failure</code> objects are sent as a <code>pb.Copyable</code> with
a class name of <q>twisted.python.failure.Failure</q>.</p>

<h2>Implementation notes</h2>

<h3>Outgoing Referenceables</h3>

<p>The side which holds the <code>Referenceable</code> uses a
ReferenceableSlicer to serialize it. Each <code>Referenceable</code> is
tracked with a <q>process-Unique ID</q> (abbreviated <q>puid</q>). As the
name implies, this number refers to a specific object within a given
process: it is scoped to the process (and is never sent to another process),
but it spans multiple PB connections (any given object will have the same
<code>puid</code> regardless of which connection is referring to it). The
<code>puid</code> is an integer, normally obtained with
<code>id(obj)</code>, but you can override the object's
<code>processUniqueID</code> method to use something else (this might be
useful for objects that are really proxies for something else). Any two
objects with the same <code>puid</code> are serialized identically.</p>

<p>All Referenceables sent over the wire (as arguments or return values for
remote methods) are given a <q>connection-local ID</q> (<code>clid</code>)
which is scoped to one end of the connection. The Referenceable is serialized
with this number, using a banana sequence of <code>(OPEN "my-reference"
clid)</code>. The remote peer (the side that holds the
<code>RemoteReference</code>) knows the <code>Referenceable</code> by the
<code>clid</code> sent to represent it. These are small integers. From a
security point of view, any object sent across the wire (and thus given a
<code>clid</code>) is forever accessible to the remote end (or at least until
the connection is dropped).</p>

<p>The sending side uses the <code>Broker.clids</code> dict to map
<code>puid</code> to <code>clid</code>. It uses the
<code>Broker.localObjects</code> dict to map <code>clid</code> to
<code>Referenceable</code>. The reference from <code>.localObjects</code>
also has the side-effect of making sure the Referenceable doesn't go out of
scope while the remote end holds a reference.</p>

<p><code>Broker.currentLocalID</code> is used as a counter to create
<code>clid</code> values.</p>


<h3>RemoteReference</h3>

<p>In response to the incoming <code>my-reference</code> sequence, the
receiving side creates a <code>RemoteReference</code> that remembers its
Broker and the <code>clid</code> value. The RemoteReference is stashed in the
<code>Broker.remoteReferences</code> weakref dictionary (which maps from
<code>clid</code> to <code>RemoteReference</code>), to make sure that a
single <code>Referenceable</code> is always turned into the same
<code>RemoteReference</code>. Note that this is not infallible: if the
recipient forgets about the <code>RemoteReference</code>, PB will too. But if
they really do forget about it, then they won't be able to tell that the
replacement is not the same as the original<span class="footnote">unless they
do something crazy like remembering the <code>id(obj)</code> of the old
object and check to see if it is the same as that of the new one. But
<code>id(obj)</code> is only unique among live objects anyway</span>. It will
have a different <code>clid</code>.<span class="footnote">and note that I
think there is a race condition here, in which the reference is sent over the
wire at the same time the other end forgets about it</span></p>

<p>This <code>RemoteReference</code> is where the <code>.callRemote</code>
method lives. When used to invoke remote methods, the <code>clid</code> is
used as the second token of a <code>call</code> sequence. In this context,
the <code>clid</code> is a <q>your-reference</q>: it refers to the
recipient's <code>.localObjects</code> table. The
<code>Referenceable</code>-holder's <code>my-reference-id</code> is sent
back to them as the <code>your-reference-id</code> argument of the
<code>call</code> sequence.</p>

<p>The <code>RemoteReference</code> isn't always used to invoke remote
methods: it could appear in an argument or a return value instead: the goal
is to have the <code>Referenceable</code>-holder see their same
<code>Referenceable</code> come back to them. In this case, the
<code>clid</code> is used in a <code>(OPEN "your-reference" clib)</code>
sequence. The <code>Referenceable</code>-holder looks up the
<code>clid</code> in their <code>.localObjects</code> table and puts the
result in the method argument or return value.</p>



<h3>URL References</h3>

<p>In addition to the implicitly-created numerically-indexed
<code>Referenceable</code> instances (kept in the Broker's
<code>.localObjects</code> dict), there are explicitly-registered
string-indexed <code>Referenceable</code>s kept in the PBServerFactory's
<code>localObjects</code> dictionary. This table is used to publish objects
to the outside world. These objects are the targets of the
<code>pb.getRemoteURL</code> and <code>pb.callRemoteURL</code>
functions.</p>

<p>To access these, a <code>URLRemoteReference</code> must be created that
refers to a string <code>clid</code> instead of a numeric one. This is a
simple subclass of <code>RemoteReference</code>: it behaves exactly the same.
The <code>URLRemoteReference</code> is created manually by
<code>pb.getRemoteURL</code>, rather than being generated automatically upon
the receipt of a <code>my-reference</code> sequence. It also assumes a list
of RemoteInterface names (which are usually provided by the holder of the
<code>Referenceable</code>).</p>

<p>To invoke methods on a URL-indexed object, a string token is used as the
<code>clid</code> in the <q>your-reference-id</q> argument of a
<code>call</code> sequence.</p>

<p>In addition, the <code>clid</code> of a <code>your-reference</code>
sequence can be a string to use URL-indexed objects as arguments or return
values of method invocations. This allows one side to send a
<code>URLRemoteReference</code> to the other and have it turn into the
matching <code>Referenceable</code> when it arrives. Of course, if it is
invalid, the method call that tried to send it will fail.</p>

<p>Note that these <code>URLRemoteReference</code> objects wil not survive a
roundtrip like regular <code>RemoteReference</code>s do. The
<code>URLRemoteReference</code> turns into a <code>Referenceable</code>, but
the <code>Referenceable</code> will turn into a regular numeric (implicit)
<code>RemoteReference</code> when it comes back. This may change in the
future as the URL-based referencing scheme is developed. It might also
become possible for string <code>clid</code>s to appear in
<code>my-reference</code> sequences, giving
<code>Referenceable</code>-holders the ability to publish URL references
explicitly.</p>

<p>It might also become possible to have these URLs point to other servers.
In this case, a <code>remote</code> sequence will probably be used, rather
than the <code>my-reference</code> sequence used for implicit
references.</p>

<p>Note that these URL-endpoints are per-Factory, so they are shared between
multiple connections (the implicitly-created references are only available
on the connection that created them). The PBServerFactory is created with a
<q>root object</q>, which is a URL-endpoint with a <code>clid</code> of an
empty string.</p>





</body> </html>
