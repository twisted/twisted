Original Proposal to use Sphinx instead of Lore for Twisted Docs
================================================================

:Author: Kevin Horn

.. note::

    The transition plan in this document is outdated.

    See: :doc:`transition_plan`

This document presents a proposal for transitioning the system for 
managing documentation of the Twisted project from the current system 
(Lore) to a new system (Sphinx).

Note that this proposal intends only to change to Sphinx for long-form,
instructional documentation, not for API documentation.  API documentation
would continue to be handled by pyDoctor for the present time.  Any 
discussion of changes to the way API docs are handled is outside the scope
of this document.

TODOs
-----
- add maintaining Twisted documentation section


Benefits to changing to Sphinx
------------------------------

* `Lots <http://sphinx.pocoo.org/examples.html>`_ of other projects use Sphinx
    - potential editors more likely to be familiar with syntax
    - third-party extensions more likley
    - Sphinx is likely to be around for  while
* No need to maintain Lore (are there any other projects using it?)
* Close lots of tickets which propose changes in Lore system and/or 
  workflow.
* Has most (all?) of the features in Lore, plus some others.
* Can be easily themed.
* Automated testing of code samples in docs
* Specific markup contructs for noting version at which paricular features 
  were added, changed, or deprecated.


Risks and Potential Drawbacks
-----------------------------

* It is possible that Sphinx could become unmaintained in the future.  
  However, this seems unlikely, since Sphinx is used for core Python docs 
  and for many other projects.
* Certain markup constructs which can be created in (x)html are invalid in
  RestructuredText.  For example, nested inline markup is not allowed, so
  something like ``<em><strong>stuff</strong></em>`` could not be literally
  translated into ReST.  It is unlikely that this will be a huge problem.


Comparison of Features
----------------------

Below is a comparison of some of the most important features of both Lore 
and Sphinx:

=====================================   ====        ======
Feature                                 Lore        Sphinx
=====================================   ====        ======
 HTML Output                             Y            Y
 LaTeX Output                            Y            Y
 Direct PDF Output                       N            Y*
 CHTML Output                            N            Y
 Code Sytax Highlighting                 Y            Y
 Automatic testing of code samples       N            Y*
 Interlink with other projects' docs     N            Y*
 Auto-generated index                    Y            Y
 JS-based search facility                N            Y
 Include external files at build time    L            Y
 Conditional inclusion of content        ?            Y
 File-wide metadata                      ?            Y
 Stable extension API                    N            Y
=====================================   ====        ======

[Y] Feature supported
[N] Feature not supported
[L] Limited support for this feature
[*] Requires Sphinx Extension

Let's examine these items further:


Output Formats
~~~~~~~~~~~~~~
Both Lore and Sphinx support HTML and LaTeX output.

Sphinx also supports CHTML output and direct PDF output.
    
    * CHTML output generates the files necessary to create Microsoft
      "compiled html" help files.  The MS help compiler from the 
      Microsoft HTML Help Workshop is however 
      required to actually build such a file.
    * Direct PDF output is available through the rst2pdf Sphinx extension 
      and requires installation of the ReportLab Toolkit.

Lore supports HTML, MagicPoint and LaTex output for slides.  However, this 
is not used for generating the current (online) Twisted docs.


Code Syntax Highlighting
~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx uses `pygments <http://pygments.org>`_ to highlight source code.  
This allows `many languages <http://pygments.org/languages/>`_ to be 
highlighted.  As of September, 2009, `pygments` is actively maintained, 
and it seems that it will be for the foreseeable future.

Lore also includes syntax highlighting functionality, but it is limited to
highlighting python.


Automatic Testing of Code Samples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx allows automated testing of code samples in the body of 
documentation using the 
`doctest <http://sphinx.pocoo.org/ext/doctest.html>`_ extension.  
This ensures that examples, tutorials, etc. are up to date.

A number of other strategies are available for testing code samples in 
Sphinx.  There are several otehr third-party testing extensions, and sample
code can be included from external files, which would allow those files to 
be tested directly.

Lore does not currently include sample code testing functionality.


Interlink with External docs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx has an extension called 
`intersphinx <http://sphinx.pocoo.org/ext/intersphinx.html>`_ which allows
referencing of documentation between Sphinx projects.  This would allow 
the Twisted Documentation to link to other projects which use Sphinx, and 
(possibly more importantly), allow other projects using Sphinx to easily 
link to the Twisted Documentation.

Lore does not currently include this functionality beyond simple 
hyperlinks.


Auto-Generated Index
~~~~~~~~~~~~~~~~~~~~
At build time, Sphinx automatically generates an index, which can be 
output along with the rest of the project, and can also be used to power a 
built-in JavaScript search facility (see below).

Additional index entries can be added by using special directives in the 
RestructuredText markup of the Sphinx source files.

Lore also includes some indexing functionality.


Javascript Search Facility
~~~~~~~~~~~~~~~~~~~~~~~~~~
For the HTML output format, Sphinx provides a JavaScript-based search 
facility, which uses the auto-generated index to locate keywords in 
generated output.

CHTML?


Include External Files at Build Time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx allows the inclusion of content from external (non Restructuredtext)
files, using the ``include`` or ``literalinclude`` directives.

Sphinx also supports including only a part of an external file.  The part 
to be included can be selected by the following methods:

    * including content before a given string present in the file to be 
      included
    * including content after a given string present in the file to be 
      included
    * including Python classes, functions or methods directly from a 
      Python source file
    * include specific lines from an external file
    
One advantage of including external files is that it allows code samples to
be stored in external files, which allows separate testing (if use of the 
`doctest <http://sphinx.pocoo.org/ext/doctest.html>`_ extension is deemed
undesirable), and prevents maintenance problems inherent in maintaining 
both docs and external files when distributing examples.

Lore allows inclusion of external files, but has only limited support for 
including partial files.


Conditional Inclusion of Content
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sphinx includes several facilities for conditional inclusion of content.
These include the ``only`` and ``todo`` directives, and the 
`ifconfig <http://sphinx.pocoo.org/ext/ifconfig.html>`_ extension.

Lore does not include this functionality.


File-wide Metadata
~~~~~~~~~~~~~~~~~~
Sphinx allows easy inclusion of file-wide metadata on each source file.
This could be used for recording the author of a file, the version of 
Twisted to which a given document applies (or was last tested with), the 
date on which the file was last modified, or any other arbitrary metadata.

The Lore format includes only specific metadata items, and Lore must be 
extended in order to accomodate further items.


Stable extension API
~~~~~~~~~~~~~~~~~~~~
Sphinx has a stable, well-documented extension API.  This has led to a set
of useful extensions which are released along with Sphinx, as well as a 
small but growing set of third-party extensions.

Lore has an extension API, but it is not well documented and seldom used.


Transition Plan
---------------

.. todo::

    see: http://twistedmatrix.com/pipermail/twisted-python/2009-November/020949.html
    
    should there be a brief "docs freeze"?
    
    address linking from Sphinx docs to API docs (and maybe vice-versa?)

.. note::

    The transition plan in this document is outdated.

    See: :doc:`transition_plan`


Phase 0 -- "make it work"
~~~~~~~~~~~~~~~~~~~~~~~~~

Initially, Lore documents will be maintained as before.  However, a
second copy of the documentation in Sphinx format will be provided in 
parallel, in a "sandbox".  This documentation will be automatically 
converted to Sphinx RestructuredText format using an automated conversion 
tool (tentatively called ``lore2sphinx``).  During this period, it is 
expected that the "sandbox"  documentation will contain errors and/or 
artifacts from the automatic conversion process, and ``lore2sphinx`` will 
be improved in order to improve the conversion process, and hopefully 
eliminate any of these conversion artifacts.  Any Lore documents which 
are difficult and/or impossible to convert using the automatic process 
should be patched (in Lore format) in order to make them easier for the 
automatic process to convert.

Once it has been verified that all Lore documents can be automatically 
converted into Sphinx RestructuredText format, a review of the Sphinx 
documentation should be conducted to determine whether the new docs are 
suitable for production use. Once the review process is complete, a 
decision will be made by the Twisted core developers to officially 
transition to the new format.  

**Timeline for Phase 0** :

    - develop lore2sphinx tool
    - develop custom Sphinx theme for Twisted docs
    - patch lore docs to make them easier to convert
    - convert lore docs to sphinx format continually and maintain in 
      a "sandbox"
    - identify branches which have lore patches in them
        - (list of branches here)
    - branches containing lore docs changes should be separated into 2 groups:
        - those which should be merged before the changeover 
          (Branch Group A)
        - those in which the lore docs changes should be converted to 
          sphinx changes (Branch Group B)
    - identify tickets which propose to fix/modify Lore functionality
    - identify wiki pages that need to be changed, and the 
      necessary changes
        - http://twistedmatrix.com/trac/wiki/ReviewingDocumentation
        - http://twistedmatrix.com/trac/wiki/ReviewProcess
        - ???
    - decide that the conversion process is "good enough"
        - all xhtml tags should be handled by the lore2sphinx tool
          (or removed by submitting lore source patches)
        - all branches in Branch Group A should have been merged into trunk
        - all patches to lore docs submitted for purposes of making the 
          conversion process easier/smoother should have been 
          applied/merged to trunk
        - at least HTML and PDF Sphinx builder should be working properly,
          with few or no Sphinx warnings, and no Sphinx errors
        - all syntax listed on the 
          `Using Lore <http://twistedmatrix.com/documents/current/lore/howto/lore.html>`_ 
          page should be handled properly
          (or intentionally ignored), at least in the general case
    - create a "sphinx-docs" branch in Twisted SVN
    - changeover!
        - commit sphinx project to Twisted trunk
        - remove lore source documents
        - publish generated Sphinx documents (HTML and PDF) to website
        - (mostly) cease development on lore2sphinx
        - update relevant wiki pages
    - merge "sphinx-docs" branch to Twisted trunk
    - close existing tickets which propose to modify lore functionality
      (and are therefore obsolete)
    - modify all existing documentation tickets to reference/use Sphinx
        - update any patches from lore source patches 
          to Sphinx source patches
        - close tickets made irrelevant by the changeover
    - branches from Branch Group B should be updated to provide changes to 
      Sphinx source instead of lore source
    - remove lore source from Twisted trunk


Phase 1 - "make it right"
~~~~~~~~~~~~~~~~~~~~~~~~~

After the official transition has taken place, the new Sphinx docs will be
the "official" documentation.  Documentation maintenance will involve 
edits/patches to the Sphinx RestructuredText files and new documents 
should be added in Sphinx format.

During this period any remaining artifacts from the automatic conversion 
process should be removed by manual editing of the Sphinx RestructuredText 
files.

**Timeline for Phase 1** : 

    - manual browsing of the docs by both Twisted developers *and* Users
        - should be an open "public feedback" time period
        - should be for a *limited time*
        - this will hopefully identify most remaining problems with the 
          new docs
        
    - manual review/edits of Sphinx source docs
        - create a ticket for each Twisted project and assign an
          editor for each.  
        - Edits should be made to resolve any 
          remaining markup artifacts present in Sphinx source.
        - any needed manual index entries should be added
        - documents should be checked for broken links
        - automatically generated ``toctree`` directives will be created 
          in alphabetical order by the conversion process.  These should 
          be modified where appropriate to be in a more natural reading 
          order.  This is mostly important as this is how Sphinx generates 
          'prev' and 'next' navigation links for each page.
        - commit these changes as per normal Twisted development 
          procedure (with reviewer signoff, etc.)


Phase 2 - "make it fast/cool/elegant/awesome/whatever"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

At this point, Sphinx-specific features should be added to the 
documentation.  This could include making Sphinx test code given in 
examples, etc.  Also, any documentation outside of Lore should be migrated 
into the new Sphinx Docs.

**Timeline for Phase 2** :

    - merge any appropriate documentation which is outside of Lore
      into the existing docs (e.g. wiki pages, etc.)
    - set up automated testing of docs example code
    - integrate API docs (make links to API docs from Sphinx)
    - fully automate the docs build and deployment process


Rollback
--------
In the event that the transition encounters unexpected problems, or the 
Twisted core developers decide not to move forward for some reason, the 
project may be abandoned at any point during Phase 0 (see above).  Because 
all documentation edits will be made to Lore documents during this phase.

Once the transition moves to Phase 1, however, rolling back from the 
transition will be considerably more difficult, as this will require 
back-porting documentation edits from Sphinx into Lore.  It is recommended 
that the decision to "pull the trigger" to move from Phase 0 to Phase 1 be 
made only once the Sphinx version of the documentation has reached a state 
where the Twisted core developers consider it unlikely that such a 
rollback will be required.

Development Work
----------------

* lore2sphinx - tool to automatically convert Lore docs to Sphinx docs
* twisted Sphinx theme
* fabric fabfile for automation of docs workflow
* Twisted Documentation Guide - a manual which will explain Twisted
  documentation pactices, tools, and workflow
* other?


Future Work
-----------
Assuming this proposal is accepted and the transition takes place,
here are some further ideas:

* migrate some stuff from the Trac wiki into the official Twisted docs
* integrate with API docs?
* create a Sphinx extension that will automatically generate links to Trac
  entities (tickets, changesets, etc.)
* `This page <http://broadcast.oreilly.com/2009/02/writing-technical-documentatio.html>`_ 
  has some stuff on using `cog <http://nedbatchelder.com/code/cog/>`_ in
  RestructuredText comments to generate the *output* of sample scripts.