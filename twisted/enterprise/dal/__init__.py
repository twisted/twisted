# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Toolkit for building a Data-Access Layer (DAL).

This includes an abstract representation of SQL objects like tables, columns,
sequences and queries, a parser to convert your schema to that representation,
and tools for working with it.

In some ways this is similar to the low levels of something like SQLAlchemy, but
it is designed to be more introspectable, to allow for features like automatic
caching and index detection.  NB: work in progress.
"""
