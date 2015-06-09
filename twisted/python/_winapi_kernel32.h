// Copyright (c) Twisted Matrix Laboratories.
// See LICENSE for details.

/*
    This file's purpose is to define the functions we wish to
    use from the kernel32 dynamic library.

    You may also #define constants for use within Twisted as well. One
    advantage of defining constants here is attempts to modify the
    constant later on, hopefully by accident, will result in an
    exception being raised.

    Take care when defining functions to provide and always research
    the functions you plan to provide.  Although Microsoft may have
    dropped support for XP it's not going away anytime soon.  Because
    of this we either need to stick to XP compatible libraries or provide
    workarounds in _winapi.py.
*/

// Process access rights
#define PROCESS_QUERY_INFORMATION 0x0400

// Error codes which are used by Twisted
#define ERROR_ACCESS_DENIED 0x5
#define ERROR_INVALID_PARAMETER 0x57

HANDLE OpenProcess(DWORD, BOOL, DWORD);
