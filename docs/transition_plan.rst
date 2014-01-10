Twisted Lore->Sphinx Transition Plan
====================================

Overall Plan
------------

- close ticket :trac:`#4239` (fixed)
- close ticket :trac:`#4336` (fixed)
- close ticket :trac:`#4348` (fixed)
- create "master ticket" in trac : Use Sphinx for Documentation

    - use script ("lore2sphinx") to convert lore docs to sphinx format

        - make sure external entities are included
        - turn off lxml parsers recover from errors functionality

    - build new sphinx docs

        - set TOC :maxdepth: to 0
        - manually fix any Sphinx markup that causes build errors

    - create a branch: "lore2sphinx-conversion-XXXX"
    - move the new sphinx docs into the branch
    - split up the docs into reasonable-size chunks

        - create a "task" ticket in trac for each chunk
        - have people grab a ticket:

            - review the rst markup of their chunk for markup errors
            - if non-markup errors are found, open a new ticket
            - if markup errors are found either:

                - apply changes to the branch to fix the errors, and close the ticket for that chunk
                - or attach a patch to the chunk-review ticket, and mark with "review" keyword

    - once all docs have been reviewed for markup errors, and all
      "chunk-tickets" closed, merge branch and close master ticket

    (at this point, all new docs should be submitted in Sphinx format)

- open a ticket for: fixing up the 'twistedtrac' sphinx theme
  (the new trac site is great, but the sphinx theme will need to be updated)
- open ticket for: deploy new docs to website
- open ticket for: update buildslaves to build new docs
- open ticket for: update documentation to reflect conversion

    - write new Twisted Documentation Guide

        - document writing sphinx docs
        - document `:api:` extension role

    - remove/replace references to Lore throughout docs
    - remove old Lore docs or update them to reflect that Lore is no
      longer actively maintained

- open ticket for: anything else???
- either close `open Lore tickets`_, or mark them as lowest priority


Proposed "chunks" for review
----------------------------

    - projects/conch
    - projects/core/development
    - projects/core/howto (except 'tutorial/')
    - projects/core/howto/tutorial
    - projects/historic
    - projects/lore
    - projects/mail
    - projects/names
    - projects/pair
    - projects/vfs
    - projects/web (everything except web-in-60)
    - projects/web/web-in-60
    - projects/web2
    - projects/words

How to review a "chunk ticket"
------------------------------

    - check out the branch_
    - build the docs (requires sphinx ~0.6.4 or so)
    - look over the docs for this chunk
        - look ONLY for markup errors, missing content, or other things related to conversion
        - be sure to look at both the `.rst` and `.html` files
        - grep for xhtml tags still in the document
          (sometimes they sneak in inside comments)
        - if you find another problem, see if there's a ticket for it
            - if there is, make a note on the chunk ticket and move on
            - if not, create a new ticket, and leave a note in the chunk ticket
        - either commit fixes back to the branch, or attach a patch to the chunk ticket


.. _4239: http://twistedmatrix.com/trac/ticket/4239
.. _4336: http://twistedmatrix.com/trac/ticket/4336
.. _4348: http://twistedmatrix.com/trac/ticket/4348
.. _open Lore tickets: http://twistedmatrix.com/trac/query?status=new&status=assigned&status=reopened&component=lore&order=priority
.. _branch: http://bitbucket.org/khorn/lore2sphinx
