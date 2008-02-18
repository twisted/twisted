# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The Twisted Documentation Generation System

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}

The general way in which Lore operates is quite simple and straightforward.  It
generally follows these steps::

    * Process configuration or command line options to create the necessary
      objects::

        * Book - an optional object which represents a sequence of documents
          (usually considered chapters) and a way to collect them together.

        * Processor - an object which can produce a document in a particular
          output format.

        * Walker - an object which will visit all of the input documents and
          invoke the processor on them.

        * Indexer - an optional object which can generate a table of terms
          linked to the location of their use in the output document.

        * Numberer - an object which will automatically assign consecutive
          increasing integers to each section in the output document.

    * A book instance is created if the configuration demands one.

    * The plugin system is queried for L{IProcessor} plugins and the first
      which matches the input document type, as specified by the configuration,
      is retrieved.  If none is found, the input document type is treated as
      the fully qualified Python name of an object to use as the processor.

    * An output generator matching the specified output format is requested
      from the processor.

    * A walker of the appropriate type is created.

    * Each input file specified is added to the walker.  If none are specified
      but a book is specified, then each file from the book is added to the
      walker.  If no book is specified, a specified directory is searched for
      input files.

    * The indexer is given a filename.

    * The walker is told to generate output for all of the files it knows
      about.

        * For each file the walker knows about, the output generator is invoked
          to write a corresponding output file.

        * The indexer is given a chance to write its output.

        * If there are any failures, they are reported.

The main entrypoint for lore is L{twisted.lore.scripts.lore}.  The
L{runGivenOptions<twisted.lore.scripts.lore.runGivenOptions>} function
implements most of the above sequence.

Books are implemented in L{twisted.lore.htmlbook}.

Processors are implemented in L{twisted.lore.default}, L{twisted.lore.lmath},
L{twisted.lore.slides}, L{twisted.lore.man2lore}, and
L{twisted.lore.nevowlore}, with L{twisted.lore.default} providing the most
developed, functional, and generally useful processor.

Walkers are implemented in L{twisted.lore.process}.

The indexer is implemented in L{twisted.lore.indexer}.

The numberer is implemented in L{twisted.lore.numberer}.
"""

# TODO
# Abstract
# Bibliography
# Index
# Allow non-web image formats (EPS, specifically)
# Allow pickle output and input to minimize parses
# Numbered headers
# Navigational aides

from twisted.lore._version import version
__version__ = version.short()
