from cffi import FFI
ffi = FFI()

ffi.cdef("""

typedef size_t HANDLE;
typedef size_t SOCKET;
typedef unsigned long DWORD;
typedef size_t ULONG_PTR;
typedef int BOOL;

typedef struct _IN_ADDR { ...; } IN_ADDR;

typedef struct _OVERLAPPED { ...; } OVERLAPPED;

typedef struct sockaddr {
    ...;
    short sa_family;
};

typedef struct sockaddr_in { ...;
    short sin_family;
    unsigned short sin_port;
    char sin_addr[4];
};
typedef struct sockaddr_in6 { ...; 
    short sin6_family;
    unsigned short sin6_port;
    char sin6_addr[16];
};


typedef struct __WSABUF {
    ULONG len;
    char *buf;
} WSABUF;

static int initialize_function_pointers(void);

BOOL AcceptEx(HANDLE, HANDLE, char*, DWORD, DWORD, DWORD, LPDWORD, OVERLAPPED*);

HANDLE CreateIoCompletionPort(HANDLE fileHandle, HANDLE existing, ULONG_PTR key, DWORD numThreads);
BOOL GetQueuedCompletionStatus(HANDLE port, DWORD *bytes, ULONG_PTR *key, intptr_t *overlapped, DWORD timeout);
BOOL PostQueuedCompletionStatus(HANDLE port, DWORD bytes, ULONG_PTR key, OVERLAPPED *ov);

BOOL Tw_ConnectEx4(HANDLE, struct sockaddr_in*, int, PVOID, DWORD, LPDWORD, OVERLAPPED*);
BOOL Tw_ConnectEx6(HANDLE, struct sockaddr_in6*, int, PVOID, DWORD, LPDWORD, OVERLAPPED*);

int WSARecv(HANDLE, struct __WSABUF* buffs, DWORD buffcount, DWORD *bytes, DWORD *flags, OVERLAPPED *ov, void *crud);

int WSARecvFrom(HANDLE s, WSABUF *buffs, DWORD buffcount, DWORD *bytes, DWORD *flags, struct sockaddr *fromaddr, int *fromlen, OVERLAPPED *ov, void *crud);

int WSASend(HANDLE s, WSABUF *buffs, DWORD buffcount, DWORD *bytes, DWORD flags, OVERLAPPED *ov, void *crud);

int WSAGetLastError(void);

HANDLE getInvalidHandle();
""")

ffi.set_source("twisted.internet.iocpreactor._iocp",
"""
#include <sys/types.h>

#define WINDOWS_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <mswsock.h>
#include <in6addr.h>


#pragma comment(lib, "Mswsock.lib")
#pragma comment(lib, "ws2_32.lib")

HANDLE getInvalidHandle() {
    return INVALID_HANDLE_VALUE;
}

static LPFN_ACCEPTEX Py_AcceptEx = NULL;
static LPFN_CONNECTEX Py_ConnectEx = NULL;
static LPFN_DISCONNECTEX Py_DisconnectEx = NULL;


#define GET_WSA_POINTER(s, x)                                           \
    (SOCKET_ERROR != WSAIoctl(s, SIO_GET_EXTENSION_FUNCTION_POINTER,    \
                              &Guid##x, sizeof(Guid##x), &Py_##x,       \
                              sizeof(Py_##x), &dwBytes, NULL, NULL))

static int
initialize_function_pointers(void)
{
    GUID GuidAcceptEx = WSAID_ACCEPTEX;
    GUID GuidConnectEx = WSAID_CONNECTEX;
    GUID GuidDisconnectEx = WSAID_DISCONNECTEX;
    SOCKET s;
    DWORD dwBytes;

    s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

    if (!GET_WSA_POINTER(s, AcceptEx) ||
        !GET_WSA_POINTER(s, ConnectEx) ||
        !GET_WSA_POINTER(s, DisconnectEx))
    {
        closesocket(s);
        return -1;
    }

    closesocket(s);

    return 0;
}

BOOL Tw_ConnectEx4(HANDLE a, struct sockaddr_in* b , int c, PVOID d, DWORD e, LPDWORD f, OVERLAPPED* g) {
    return Py_ConnectEx(a, b, c, d, e, f, g);
}
BOOL Tw_ConnectEx6(HANDLE a, struct sockaddr_in6* b , int c, PVOID d, DWORD e, LPDWORD f, OVERLAPPED* g) {
    return Py_ConnectEx(a, b, c, d, e, f, g);
}

""")


if __name__ == "__main__":
    ffi.compile()