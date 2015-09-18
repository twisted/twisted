
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Writing Standard
========================

The Twisted writing standard describes the documentation writing
styles we prefer in our documentation. This standard applies particularly
to howtos and other descriptive documentation.

This document is meant to help Twisted documentation authors produce
documentation that does not have the following problems:

- misleads users about what is good Twisted style;
- misleads users into thinking that an advanced howto is an introduction
  to writing their first Twisted server; and
- misleads users about whether they fit the document's target audience:
  for example, that they are able to use enterprise without knowing how to
  write SQL queries.


General style
-------------

Documents should aim to be clear and concise, allowing the API
documentation and the example code to tell as much of the story as they
can. Demonstrations and where necessary supported arguments should always
preferred to simple statements ("here is how you would simplify this
code with Deferreds" rather than "Deferreds make code
simpler").

Documents should be clearly delineated into sections and subsections.
Each of these sections, like the overall document, should have a single
clear purpose. This is most easily tested by trying to have meaningful
headings: a section which is headed by "More details" or
"Advanced stuff" is not purposeful enough. There should be
fairly obvious ways to split a document. The two most common are task
based sectioning and sectioning which follows module and class
separations.

Documentation must use American English spelling, and where possible
avoid any local variants of either vocabulary or grammar. Grammatically
complex sentences should ideally be avoided: these make reading
unnecessarily difficult, particularly for non-native speakers.

When referring to a hypothetical person, (such as "a user of a website written with twisted.web"), gender neutral pronouns (they/their/them) should be used.

For reStructuredText documents which are handled by the Sphinx documentation generator make lines short, and break lines at natural places, such as after commas and semicolons, rather than after the 79th column.
We call this *semantic newlines*.
This rule **does not** apply to docstrings.

..  code-block:: text
    :linenos:

    Sometimes when editing a narrative documentation file, I wrap the lines semantically.
    Instead of inserting a newline at 79 columns (or whatever),
    or making paragraphs one long line,
    I put in newlines at a point that seems logical to me.
    Modern code-oriented text editors are very good at wrapping and arranging long lines.


Evangelism and usage documents
------------------------------


    
The Twisted documentation should maintain a reasonable distinction
between "evangelism" documentation, which compares the Twisted
design or Twisted best practice with other approaches and argues for the
Twisted approach, and "usage" documentation, which describes the
Twisted approach in detail without comparison to other possible
approaches.

    


While both kinds of documentation are useful, they have different
audiences. The first kind of document, evangelical documents, is useful to
a reader who is researching and comparing approaches and seeking to
understand the Twisted approach or Twisted functionality in order to
decide whether it is useful to them. The second kind of document, usage
documents, are useful to a reader who has decided to use Twisted and
simply wants further information about available functions and
architectures they can use to accomplish their goal.

    


Since they have distinct audiences, evangelism and detailed usage
documentation belongs in separate files. There should be links between
them in 'Further reading' or similar sections.

    



Descriptions of features
------------------------


    
Descriptions of any feature added since release 2.0 of Twisted core
must have a note describing which release of which Twisted project they
were added in at the first mention in each document. If they are not yet
released, give them the number of the next minor release.

    


For example, a substantial change might have a version number added in
the introduction:

    

    
    
    This document describes the Application infrastructure for deploying
    Twisted applications *(added in Twisted 1.3)* .
    
    
        
    
The version does not need to be mentioned elsewhere in the document
except for specific features which were added in subsequent releases,
which might should be mentioned separately.

    

    
    
    The simplest way to create a ``.tac`` file, SuperTac *(added in Twisted Core 99.7)* ...
    
        
    
In the case where the usage of a feature has substantially changed, the
number should be that of the release in which the current usage became
available. For example:

    

    
    This document describes the Application infrastructure for
    deploying Twisted applications *(updated[/substantially updated] in Twisted 2.7)* .  
    
        
    

Linking
-------


The first occurrence of the name of any module, class or function should
always link to the API documents. Subsequent mentions may or may not link
at the author's discretion: discussions which are very closely bound to a
particular API should probably link in the first mention in the given
section.

Links between howtos are encouraged. Overview documents and tutorials
should always link to reference documents and in depth documents. These
documents should link among themselves wherever it's needed: if you're
tempted to re-describe the functionality of another module, you should
certainly link instead.

Linking to standard library documentation is also encouraged when referencing
standard library objects. `Intersphinx <http://sphinx-doc.org/ext/intersphinx.html>`_
is supported in Twisted documentation, with prefixes for linking to either
the Python 2 standard library documentation (via ``py2``) or Python 3 (via
``py3``) as needed.


Introductions
-------------


    
The introductory section of a Twisted howto should immediately follow
the top-level heading and precede any subheadings.

    


The following items should be present in the introduction to Twisted
howtos: the introductory paragraph and the description of the target
audience.

    



Introductory paragraph
~~~~~~~~~~~~~~~~~~~~~~


    
The introductory paragraph of a document should summarize what the
document is designed to present. It should use the both proper names for
the Twisted technologies and simple non-Twisted descriptions of the
technologies. For example, in this paragraph both the name of the technology
("Conch") and a description ("SSH server") are used:

    

    
    
    This document describes setting up a SSH server to serve data from the
    file system using Conch, the Twisted SSH implementation.
    
    
        
    
The introductory paragraph should be relatively short, but should, like
the above, somewhere define the document's objective: what the reader
should be able to do using instructions in the document.

    



Description of target audience
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    
Subsequent paragraphs in the introduction should describe the target
audience of the document: who would want to read it, and what they should
know before they can expect to use your document. For example:

    

    
    
    
    
    The target audience of this document is a Twisted user who has a set of
    filesystem like data objects that they would like to make available to
    authenticated users over SFTP.
    
    
    
    
    
    
    Following the directions in this document will require that you are
    familiar with managing authentication via the Twisted Cred system.
    
    
    
    
    
        
    
Use your discretion about the extent to which you list assumed
knowledge. Very introductory documents that are going to be among a
reader's first exposure to Twisted will even need to specify that they
rely on knowledge of Python and of certain networking concepts (ports,
servers, clients, connections) but documents that are going to be sought
out by existing Twisted users for particular purposes only need to specify
other Twisted knowledge that is assumed.

    


Any knowledge of technologies that wouldn't be considered "core
Python" and/or "simple networking" need to be explicitly
specified, no matter how obvious they seem to someone familiar with the
technology. For example, it needs to be stated that someone using
enterprise should know SQL and should know how to set up and populate
databases for testing purposes.

    


Where possible, link to other documents that will fill in missing
knowledge for the reader. Linking to documents in the Twisted repository
is preferred but not essential.

    



Goals of document
~~~~~~~~~~~~~~~~~


    
The introduction should finish with a list of tasks that the user can
expect to see the document accomplish. These tasks should be concrete
rather than abstract, so rather than telling the user that they will
"understand Twisted Conch", you would list the specific tasks
that they will see the document do. For example:

    

    
    
    
    
    This document will demonstrate the following tasks using Twisted Conch:
    
    
    
    
    
    
    
    - creating an anonymous access read-only SFTP server using a filesystem
      backend;
    - creating an anonymous access read-only SFTP server using a proxy
      backend connecting to an HTTP server; and
    - creating a anonymous access read and write SFTP server using a
      filesystem backend.
    
    
    
    
    
        
    
In many cases this will essentially be a list of your code examples,
but it need not be. If large sections of your code are devoted to design
discussions, your goals might resemble the following:

    

    
    
    
    
    This document will discuss the following design aspects of writing Conch
    servers:
    
    
    
    
    
    
    
    - authentication of users; and
    - choice of data backends.
    
    
    
    
    
    
        
    

Example code
------------


    
Wherever possible, example code should be provided to illustrate a
certain technique or piece of functionality.

    


Example code should try and meet as many of the following requirements
as possible:

    




- example code should be a complete working example suitable for copying
  and pasting and running by the reader (where possible, provide a link to a
  file to download);
- example code should be short;
- example code should be commented very extensively, with the assumption
  that this code may be read by a Twisted newcomer;
- example code should conform to the :doc:`coding standard <coding-standard>` ; and
- example code should exhibit 'best practice', not only for dealing with
  the target functionality, but also for use of the application framework
  and so on.


    


The requirement to have a complete working example will occasionally
impose upon authors the need to have a few dummy functions: in Twisted
documentation the most common example is where a function is needed to
generate a Deferred and fire it after some time has passed. An example
might be this, where :api:`twisted.internet.task.deferLater <deferLater>` is used to fire a callback
after a period of time:

    



.. code-block:: python

    
    from twisted.internet import task, reactor
    
    def getDummyDeferred():
        """
        Dummy method which returns a deferred that will fire in 5 seconds with
        a result
        """
        return task.deferLater(reactor, 5, lambda x: "RESULT")



    
As in the above example, it is imperative to clearly mark that the
function is a dummy in as many ways as you can: using ``Dummy`` in
the function name, explaining that it is a dummy in the docstring, and
marking particular lines as being required to create an effect for the
purposes of demonstration. In most cases, this will save the reader from
mistaking this dummy method for an idiom they should use in their Twisted
code.
    
    



Conclusions
-----------


    
The conclusion of a howto should follow the very last section heading
in a file. This heading would usually be called "Conclusion".

    


The conclusion of a howto should remind the reader of the tasks that
they have done while reading the document. For example:

    

    
    
    
    
    In this document, you have seen how to:
    
    
    
    
    
    
    #. set up an anonymous read-only SFTP server;
    #. set up a SFTP server where users authenticate;
    #. set up a SFTP server where users are restricted to some parts of the
       filesystem based on authentication; and
    #. set up a SFTP server where users have write access to some parts of
       the filesystem based on authentication.
    
    
    
    
        
    
If appropriate, the howto could follow this description with links to
other documents that might be of interest to the reader with their
newfound knowledge. However, these links should be limited to fairly
obvious extensions of at least one of the listed tasks.

  

