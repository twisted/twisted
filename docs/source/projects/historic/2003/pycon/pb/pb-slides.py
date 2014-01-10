#! /usr/bin/python

from slides import Lecture, NumSlide, Slide, Bullet, SubBullet, PRE, URL

class Raw:
    def __init__(self, title, html):
        self.title = title
        self.html = html
    def toHTML(self):
        return self.html

class HTML(Raw):
    def __init__(self, html):
        self.html = html

server_lore = """<div class="py-listing">
<pre><span class="py-src-keyword">class</span> <span class="py-src-identifier">ServerObject</span><span class="py-src-op">(</span><span class="py-src-parameter">pb</span><span class="py-src-op">.</span><span class="py-src-parameter">Referenceable</span><span class="py-src-op">)</span><span class="py-src-op">:</span><span class="py-src-newline"></span>
<span class="py-src-indent">    </span><span class="py-src-keyword">def</span> <span class="py-src-identifier">remote_add</span><span class="py-src-op">(</span><span class="py-src-parameter">self</span><span class="py-src-op">,</span> <span class="py-src-parameter">one</span><span class="py-src-op">,</span> <span class="py-src-parameter">two</span><span class="py-src-op">)</span><span class="py-src-op">:</span><span class="py-src-newline">
</span><span class="py-src-indent">        </span><span class="py-src-variable">answer</span> <span class="py-src-op">=</span> <span class="py-src-variable">one</span> <span class="py-src-op">+</span> <span class="py-src-variable">two</span><span class="py-src-newline">
</span>        <span class="py-src-keyword">print</span> <span class="py-src-string">&quot;returning result:&quot;</span><span class="py-src-op">,</span> <span class="py-src-variable">answer</span><span class="py-src-newline">
</span>        <span class="py-src-keyword">return</span> <span class="py-src-variable">answer</span><span class="py-src-endmarker"></span></pre>
<div class="py-caption">Server Code</div>
</div>
"""

client_lore = """<div class="py-listing"><pre>
<span class="py-src-nl"></span>    <span class="py-src-dedent"></span><span class="py-src-keyword">def</span> <span class="py-src-identifier">got_RemoteReference</span><span class="py-src-op">(</span><span class="py-src-parameter">remoteref</span><span class="py-src-op">)</span><span class="py-src-op">:</span><span class="py-src-newline">
</span>        <span class="py-src-keyword">print</span> <span class="py-src-string">&quot;asking it to add&quot;</span><span class="py-src-newline">
</span>        <span class="py-src-variable">deferred</span> <span class="py-src-op">=</span> <span class="py-src-variable">remoteref</span><span class="py-src-op">.</span><span class="py-src-variable">callRemote</span><span class="py-src-op">(</span><span class="py-src-string">&quot;add&quot;</span><span class="py-src-op">,</span> <span class="py-src-number">1</span><span class="py-src-op">,</span> <span class="py-src-number">2</span><span class="py-src-op">)</span><span class="py-src-newline">
</span>        <span class="py-src-variable">deferred</span><span class="py-src-op">.</span><span class="py-src-variable">addCallbacks</span><span class="py-src-op">(</span><span class="py-src-variable">add_done</span><span class="py-src-op">,</span> <span class="py-src-variable">err</span><span class="py-src-op">)</span><span class="py-src-newline">
</span>        <span class="py-src-comment"># this Deferred fires when the method call is complete
</span>    <span class="py-src-dedent"></span><span class="py-src-keyword">def</span> <span class="py-src-identifier">add_done</span><span class="py-src-op">(</span><span class="py-src-parameter">result</span><span class="py-src-op">)</span><span class="py-src-op">:</span><span class="py-src-newline">
</span><span class="py-src-indent">        </span><span class="py-src-keyword">print</span> <span class="py-src-string">&quot;addition complete, result is&quot;</span><span class="py-src-op">,</span> <span class="py-src-variable">result</span><span class="py-src-newline">
</span><span class="py-src-endmarker"></span></pre><div class="py-caption">Client Code</div></div>
"""

    
# title graphic: PB peanut butter jar, "Twist(ed)" on lid
lecture = Lecture(
    "Perspective Broker: Translucent RPC in Twisted",
    # intro
    Raw("Title", """
    <h1>Perspective Broker: Translucent RPC in Twisted</h1>
    <h2>PyCon 2003</h2>
    <h2>Brian Warner &lt; warner @ lothar . com &gt; </h2>
    """),

    Slide("Introduction",
          Bullet("Overview/definition of RPC"),
          Bullet("What is Perspective Broker?"),
          Bullet("How do I use it?"),
          Bullet("Security Issues"),
          Bullet("Future Directions"),
          ),
    
    Slide("Remote Procedure Calls",
          Bullet("Action at a distance: separate processes, safely telling each other what to do",
                 SubBullet("Separate memory spaces"),
                 SubBullet("Usually on different machines"),
                 ),
          Bullet("Frequently called RMI these days: Remote Method Invocation"),
          Bullet("Three basic parts: Addressing, Serialization, Waiting"),
          ),

    Slide("Addressing",
          Bullet("What program are you talking to?",
                 SubBullet("hostname, port number"),
                 SubBullet("Some systems use other namespaces: sunrpc")
                 ),
          Bullet("Which object in that program?"),
          Bullet("Which method do you want to run?"),
          Bullet("Related issues",
                 SubBullet("How do you know what the arguments are?"),
                 SubBullet("(do you care?)"),
                 SubBullet("How do you know what methods are available?"),
                 SubBullet("(do you care?)"),
                 ),
          ),

    Slide("Serialization",
          Bullet("What happens to the arguments you send in?"),
          Bullet("What happens to the results that are returned?",
                 SubBullet("Representation differences: endianness, word length"),
                 SubBullet("Dealing with user-defined types"),
                 ),
          Bullet("How to deal with references"),
          ),
    Slide("The Waiting (is the hardest part)",
          Bullet("Asynchronous: results come later, or not at all"),
          Bullet("Need to do other work while waiting"),
          ),
    
    Slide("Whither Translucence?",
          Bullet("Not 'Transparent': don't pretend remote objects are really local",
                 SubBullet("CORBA (in C) does this, makes remote calls look like local calls"),
                 SubBullet("makes it hard to deal with the async nature of RPC"),
                 ),
          Bullet("Not 'Opaque': make it easy to deal with the differences",
                 SubBullet("Including extra failure modes, delayed results"),
                 ),
          
          Bullet("Exceptions and Deferreds to the rescue")),

    Slide("Other RPC protocols",
          Bullet("HTML"),
          Bullet("XML-RPC"),
          Bullet("CORBA"),
          Bullet("when you control both ends of the wire, use PB"),
          ),
    
    Raw("Where does PB fit?",
        """<h2>PB sits on top of <span class=\"py-src-identifier\">twisted.internet</span></h2>
        <img src=\"twisted-overview.png\" />
        """),
    
    Slide("pb.RemoteReference",
          Bullet(HTML("<span class=\"py-src-identifier\">pb.Referenceable</span>: Object which can be accessed by remote systems."),
                 SubBullet(HTML("Defines methods like <span class=\"py-src-identifier\">remote_foo</span> and <span class=\"py-src-identifier\">remote_bar</span> which can be invoked remotely.")),
                 SubBullet(HTML("Methods without the <span class=\"py-src-identifier\">remote_</span> prefix are local-only.")),
                 ),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.RemoteReference</span>: Used by distant program to invoke methods."),
                 SubBullet(HTML("Offers <span class=\"py-src-identifier\">.callRemote()</span> to trigger remote method on a corresponding <span class=\"py-src-identifier\">pb.Referenceable</span>.")),
                 ),
          ),

    Raw("Sample code",
        "<h2>Sample Code</h2>" + server_lore + client_lore),
    #Slide("Simple Demo"),
    # "better demo: manhole, or reactor running in another thread"

    #build up from callRemote?
    Slide("What happens to those arguments?",
          Bullet("Basic structures should travel transparently",
                 SubBullet("Actually quite difficult in some languages"),
                 ),
          Bullet("Object graph should remain the same",
                 SubBullet("Serialization context"),
                 SubBullet("(same issues as Pickle)")),
          Bullet("Instances of user-defined classes require more care",
                 SubBullet("User-controlled unjellying"),)
          ),

    #serialization (skip banana)
    Slide("40% More Sandwich Puns Than The Leading Brand",
          Bullet("twisted.spread: python package holding other modules"),
          Bullet("PB: remote method invocation"),
          Bullet("Jelly: mid-level object serialization"),
          Bullet("Banana: low-level serialization of s-expressions"),
          Bullet("Taster: security context, decides what may be received"),
          Bullet("Marmalade: like Jelly, but involves XML, so it's bitter"),
          Bullet("better than the competition",
                 SubBullet("CORBA: few or no sandwich puns"),
                 SubBullet("XML-RPC: barely pronounceable"),
                 ),
          ),

    Slide("Jellying objects",
          Bullet("'Jellying' vs 'Unjellying'"),
          Bullet("Immutable objects are copied whole"),
          Bullet("Mutable objects get reference IDs to insure shared references remain shared",
                 SubBullet("(within the same Jellying context)")),
          ),

    Slide("Jellying instances",
          Bullet(HTML("User classes inherit from one of the <span class=\"py-src-identifier\">pb.flavor</span> classes")),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.Referenceable</span>: methods can be called remotely")),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.Copyable</span>: contents are selectively copied")),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.Cacheable</span>: contents are copied and kept up to date")),
          Bullet(HTML("Classes define <span class=\"py-src-identifier\">.getStateToCopy</span> and other methods to restrict exported state")),
          ),

    Slide("pb.Copyable example",
          PRE("""class SenderPond(FrogPond, pb.Copyable):
    def getStateToCopy(self):
        d = self.__dict__.copy()
        d['frogsAndToads'] = d['numFrogs'] + d['numToads']
        del d['numFrogs']
        del d['numToads']
        return d

class ReceiverPond(pb.RemoteCopy):
    def setCopyableState(self, state):
        self.__dict__ = state
        self.localCount = 12
    def count(self):
        return self.frogsAndToads

pb.setUnjellyableForClass(SenderPond, ReceiverPond)
""")),          
    
    Slide("Secure Unjellying",
          Bullet("Pickle has security problems",
                 SubBullet("Pickle will import any module the sender requests."),
                 SubBullet(HTML("2.3 gave up, removed safety checks like <span class=\"py-src-identifier\">__safe_for_unpickling__</span> .")),
                 ),
          Bullet("Jelly attempts to be safe in the face of hostile clients",
                 SubBullet("All classes rejected by default"),
                 SubBullet(HTML("<span class=\"py-src-identifier\">registerUnjellyable()</span> used to accept safe ones")),
                 SubBullet(HTML("Registered classes define <span class=\"py-src-identifier\">.setCopyableState</span> and others to process remote state")),
                 ),
          Bullet("Must mark (by subclassing) to transmit"),
          ),
    
    Slide("Transformation of references in transit",
          Bullet("All referenced objects get turned into their counterparts as they go over the wire"),
          Bullet("References are followed recursively",
                 SubBullet("Sending a reference to a tree of objects will cause the whole thing to be transferred"),
                 SubBullet("(subject to security restrictions)"),
                 ),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.flavors</span> get reference ids"),
                 SubBullet("They are recognized when they return, transformed into the original reference"),
                 SubBullet("Reference ids are scoped to the connection"),
                 SubBullet("One side-effect: no 'third party' references"),
                 ),
          ),

    Slide("Perspectives: pb.cred and the Identity/Service model",
          Bullet("A layer to provide common authentication services to Twisted applications"),
          Bullet(HTML("<span class=\"py-src-identifier\">Identity</span>: named user accounts with passwords")),
          Bullet(HTML("<span class=\"py-src-identifier\">Service</span>: something a user can request access to")),
          Bullet(HTML("<span class=\"py-src-identifier\">Perspective</span>: user accessing a service")),
          Bullet(HTML("<span class=\"py-src-identifier\">pb.Perspective</span>: first object, a <span class=\"py-src-identifier\">pb.Referenceable</span> used to access everything else")),
          ),
    #picture would help

    Slide("Future directions",
          Bullet("Other language bindings: Java, elisp, Haskell, Scheme, JavaScript, OCaml"),
          # donovan is doing the JavaScript port
          Bullet("Other transports: UDP, Airhook"),
          Bullet("Componentization"),
          Bullet("Performance improvements: C extension for Jelly"),
          Bullet("Refactor addressing model: PB URLs"),
          ),

    Slide("Questions", Bullet("???")),

    )

lecture.renderHTML("slides", "slide-%02d.html", css="stylesheet.css")

