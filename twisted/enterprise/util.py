# -*- test-case-name: twext.enterprise.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities for dealing with different databases.
"""

from datetime import datetime

SQL_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"



def parseSQLTimestamp(ts):
    """
    Parse an SQL timestamp string.
    """
    # Handle case where fraction seconds may not be present
    if not isinstance(ts, datetime):
        if len(ts) < len(SQL_TIMESTAMP_FORMAT):
            ts += ".0"
        return datetime.strptime(ts, SQL_TIMESTAMP_FORMAT)
    else:
        return ts



def mapOracleOutputType(column):
    """
    Map a single output value from cx_Oracle based on some rules and
    expectations that we have based on the pgdb bindings.

    @param column: a single value from a column.

    @return: a converted value based on the type of the input; oracle CLOBs and
        datetime timestamps will be converted to strings, unicode values will
        be converted to UTF-8 encoded byte sequences (C{str}s), and floating
        point numbers will be converted to integer types if they are integers.
        Any other types will be left alone.
    """
    if hasattr(column, "read"):
        # Try to detect large objects and format convert them to
        # strings on the fly.  We need to do this as we read each
        # row, due to the issue described here -
        # http://cx-oracle.sourceforge.net/html/lob.html - in
        # particular, the part where it says "In particular, do not
        # use the fetchall() method".
        column = column.read()

    elif isinstance(column, float):
        # cx_Oracle maps _all_ numbers to float types, which is more
        # consistent, but we expect the database to be able to store integers
        # as integers (in fact almost all the values in our schema are
        # integers), so we map those values which exactly match back into
        # integers.
        if int(column) == column:
            return int(column)
        else:
            return column

    if isinstance(column, unicode):
        # Finally, we process all data as UTF-8 byte strings in order to reduce
        # memory consumption.  Pass any unicode string values back to the
        # application as unicode.
        column = column.encode("utf-8")

    return column
