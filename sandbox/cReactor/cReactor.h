/*
 * Twisted, the Framework of Your Internet
 * Copyright (C) 2001-2002 Matthew W. Lefkowitz
 * 
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of version 2.1 of the GNU Lesser General Public
 * License as published by the Free Software Foundation.
 * 
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 */
/* cReactor.h */

/* includes */
#include "Python.h"
#include <sys/poll.h>
#include <pthread.h>

/* Remove unused parameter warnings. */
#define UNUSED(x) ((void)x)

/* Named constants */
enum
{
    CREACTOR_NUM_EVENT_PHASES   = 3,
};

/* System event phases. */
typedef enum _cReactorEventPhase
{
    CREACTOR_EVENT_PHASE_BEFORE     = 0,
    CREACTOR_EVENT_PHASE_DURING     = 1,
    CREACTOR_EVENT_PHASE_AFTER      = 2,
} cReactorEventPhase;

/* Reactor states. */
typedef enum _cReactorState
{
    CREACTOR_STATE_STOPPED  = 0,
    CREACTOR_STATE_RUNNING  = 1,
    CREACTOR_STATE_STOPPING = 2,
} cReactorState;

/* Transport states. */
typedef enum _cReactorTransportState
{
    CREACTOR_TRANSPORT_STATE_ACTIVE     = 0,
    CREACTOR_TRANSPORT_STATE_CLOSING    = 1,
    CREACTOR_TRANSPORT_STATE_CLOSED     = 2,
} cReactorTransportState;

/* Forward delcare types. */
typedef struct _cDelayedCall cDelayedCall;
typedef struct _cReactorMethod cReactorMethod;
typedef struct _cReactorBuffer cReactorBuffer;
typedef struct _cReactorTransport cReactorTransport;
typedef struct _cReactor cReactor;
typedef struct _cReactorJob cReactorJob;
typedef struct _cReactorJobQueue cReactorJobQueue;
typedef struct _cReactorThread cReactorThread;
typedef struct _cEventTriggers cEventTriggers;

/* Job types */
typedef enum _cReactorJobType
{
    CREACTOR_JOB_APPLY      = 1,
    CREACTOR_JOB_EXIT       = 2,
} cReactorJobType;

struct _cReactorJob
{
    /* Linkage */
    cReactorJob *       next;

    /* The type of job (determines what to use out of the union) */
    cReactorJobType     type;

    union
    {
        struct 
        {
            PyObject *  callable;
            PyObject *  args;
            PyObject *  kw;
        } apply;
    } u;
};

/* Job queue. */
struct _cReactorJobQueue
{
    /* The lock protecting the condition variable and the list of jobs. */
    pthread_mutex_t     lock;

    /* The condition variable that gets signaled when a job is placed onto the
     * job queue.
     */
    pthread_cond_t      cond;

    /* A list of jobs to run. */
    cReactorJob *       jobs;
};

/* A thread. */
struct _cReactorThread
{
    /* For thread pool linkage. */
    cReactorThread *        next;

    /* The pthread thread id. */
    pthread_t               thread_id;

    /* A link back to the reactor. */
    cReactor *              reactor;

    /* The shared interpreter state.  This is needed when creating a
     * PyThreadState when this thread begins execution.
     */
    PyInterpreterState *    interp;
};

/* The transport functions. */
typedef void (* cReactorTransportReadFunc)(cReactorTransport *transport);
typedef void (* cReactorTransportWriteFunc)(cReactorTransport *transport);
typedef void (* cReactorTransportCloseFunc)(cReactorTransport *transport);
typedef PyObject * (* cReactorTransportGetPeerFunc)(cReactorTransport *transport);
typedef PyObject * (* cReactorTransportGetHostFunc)(cReactorTransport *transport);

/* The Transport object. */
struct _cReactorTransport
{
    PyObject_HEAD
   
    /* Linkage for the list of Transports. */
    cReactorTransport * next;

    /* The state of this transport. */
    cReactorTransportState state;

    /* The file descriptor. */
    int         fd;

    /* A pointer to the poll() event mask that is being used for this
     * transport.
     */
    short *     event_mask;

    /* Transport implementation details. */
    cReactorTransportReadFunc      do_read;
    cReactorTransportWriteFunc     do_write;
    cReactorTransportCloseFunc     do_close;
    cReactorTransportGetPeerFunc   get_peer;
    cReactorTransportGetHostFunc   get_host;

    /* The outgoing buffer. */
    cReactorBuffer *    out_buf;

    /* Optional PyObject to associate with this transport. */
    PyObject *          object;

    /* A reference back to the reactor this transport is part of. */
    cReactor *          reactor;

    /* An optional producer for this transport. */
    PyObject *          producer;
    int                 producer_streaming;
};

/* a delayed call */
struct _cDelayedCall
{
    PyObject_HEAD

    /* A reference to the reactor this is a part of. NULL if unscheduled */
    cReactor *          reactor;

    /* Absolute time when the call should be fired. */
    struct timeval      call_time;

    /* The function and args to call when we are fired. */
    PyObject *          callable;
    PyObject *          args;
    PyObject *          kw;

    /* Set to 1 once the call is fired and de-scheduled */
    int                 called;

    struct _cDelayedCall *      next;
};


/* The cReactor object. */
struct _cReactor
{
    PyObject_HEAD

    /* The state this reactor is in. */
    cReactorState       state;

    /* The control pipe (for breaking out of poll). */
    int                 ctrl_pipe;

    /* A dictionary of attributes. */
    PyObject *          attr_dict;

    /* The main list of timed methods. */
    cDelayedCall *      timed_methods;

    /* A list of event types and methods for each phase. */
    cEventTriggers *    event_triggers;

    /* A list of Transports. */
    cReactorTransport * transports;
    unsigned int        num_transports;

    /* An array of pollfd structs. */
    struct pollfd *     pollfd_array;
    unsigned int        pollfd_size;

    /* A flag indicating that the pollfd array is stale. */
    int                 pollfd_stale;

    /* Flag indicating whether we are in multithread mode. */
    int                 multithreaded;

    /* The main thread's job queue. */
    cReactorJobQueue *  main_queue;

    /* The thread pool, the worker thread job queue, and the requested pool
     * size.
     */
    cReactorThread *    thread_pool;
    cReactorJobQueue *  worker_queue;
    int                 req_thread_pool_size;
};


/* Create a new cReactor. */
PyObject * cReactor_New(void);

PyObject * cReactor_resolve(PyObject *self, PyObject *args, PyObject *kw);
PyObject * cReactor_run(PyObject *self, PyObject *args);
PyObject * cReactor_stop(PyObject *self, PyObject *args);
void       cReactor_stop_finish(cReactor *reactor);
PyObject * cReactor_crash(PyObject *self, PyObject *args);
PyObject * cReactor_iterate(PyObject *self, PyObject *args, PyObject *kw);
PyObject * cReactor_fireSystemEvent(PyObject *self, PyObject *args);
PyObject * cReactor_addSystemEventTrigger(PyObject *self, PyObject *args, PyObject *kw);
PyObject * cReactor_removeSystemEventTrigger(PyObject *self, PyObject *args);
void fireSystemEvent_internal(cReactor *reactor, const char *event_type);
void cSystemEvent_FreeTriggers(cEventTriggers *triggers);

/* Create a new Transport. */
cReactorTransport * cReactorTransport_New(cReactor *reactor,
                                          int fd,
                                          cReactorTransportReadFunc do_read,
                                          cReactorTransportWriteFunc do_write,
                                          cReactorTransportCloseFunc do_close);

/* The read/write/close methods. */
void cReactorTransport_Read(cReactorTransport *transport);
void cReactorTransport_Write(cReactorTransport *transport);
void cReactorTransport_Close(cReactorTransport *transport);

/* Create a new buffer using the given size as the starting size. */
cReactorBuffer * cReactorBuffer_New(unsigned int size);

/* Destroy a previously created buffer. */
void cReactorBuffer_Destroy(cReactorBuffer *buffer);

/* Write some data into the buffer. */
void cReactorBuffer_Write(cReactorBuffer *buffer, const void *data, unsigned int size);

/* Return the number of bytes contained in the buffer. */
unsigned int cReactorBuffer_DataAvailable(cReactorBuffer *buffer);

/* Return the internal pointer to the buffer's data. */
const unsigned char * cReactorBuffer_GetPtr(cReactorBuffer *buffer);

/* Skip over 'forward' number of bytes. */
void cReactorBuffer_Seek(cReactorBuffer *buffer, unsigned int forward);

/* Emulate "from a.b import c" */
PyObject * cReactorUtil_FromImport(const char *name, const char *from_item);

/* Create an __implements__ tuple from the given class names. */
PyObject * cReactorUtil_MakeImplements(const char **names, unsigned int num_names);

/* Create a new instance of a Deferred. */
PyObject * cReactorUtil_CreateDeferred(void);

/* Convert a python number object into a millisecond delay. */
int cReactorUtil_ConvertDelay(PyObject *delay_obj);

/* Add a method to the given DelayedCall list using the given delay (in
   milliseconds). */
cDelayedCall *cReactorUtil_AddDelayedCall(cReactor *reactor,
                                          int delay_ms,
                                          PyObject *callable,
                                          PyObject *args,
                                          PyObject *kw);

void cReactorUtil_InsertDelayedCall(cReactor *reactor, cDelayedCall *call);
int cReactorUtil_RemoveDelayedCall(cReactor *reactor, cDelayedCall *call);
int cReactorUtil_ReInsertDelayedCall(cReactor *reactor, cDelayedCall *call);

/* Return the number of milliseconds until the next method need to be run. */
int cReactorUtil_NextMethodDelay(cReactor *reactor);

/* Add a method to the given method list.  Return the call ID of the method.
 */
int cReactorUtil_AddMethod(cReactorMethod **list,
                           PyObject *callable,
                           PyObject *args,
                           PyObject *kw);

/* Remove a method from the given method list.  Returns -1 on error and raises
 * ValueError.
 */
int cReactorUtil_RemoveMethod(cReactorMethod **list, int call_id);

/* Run all methods up to now.  This will return the time difference between
 * now and the next method (in milliseconds).  A negative value means
 * there are no more methods.
 */
int cReactorUtil_RunDelayedCalls(cReactor *reactor);

/* Iterate over the methods in the given method list. */
typedef void (*cReactorMethodListIterator)(PyObject *callable,
                                           PyObject *args,
                                           PyObject *kw,
                                           void *user_data);

void cReactorUtil_ForEachMethod(cReactorMethod *list,
                                cReactorMethodListIterator func,
                                void *user_data);

/* Destroy the given method list. */
void cReactorUtil_DestroyMethods(cReactorMethod *list);
void cReactorUtil_DestroyDelayedCalls(cReactor *reactor);

/* Convert event phase from string to enum. */
int cReactorUtil_GetEventPhase(const char *str, cReactorEventPhase *out_phase);

/* Raise NotImplemented. */
PyObject * cReactor_not_implemented(PyObject *self, PyObject *args, const char *text);

/* Add an active transport to the reactor.  This steals a reference to the
 * given Transport.
 */
void cReactor_AddTransport(cReactor *reactor, cReactorTransport *transport);

/* Schedule a method to be called at a later time. */
PyObject * cReactorTime_callLater(PyObject *self, PyObject *args, PyObject *kw);

/* Cancel a previously scheduled method. Deprecated. */
PyObject * cReactorTime_cancelCallLater(PyObject *self, PyObject *args);

/* Retrieve a list of pending DelayedCall objects. */
PyObject * cReactorTime_getDelayedCalls(PyObject *self, PyObject *args);

/* Create a TCP IListeningPort. */
PyObject * cReactorTCP_listenTCP(PyObject *self, PyObject *args, PyObject *kw);

/* XXX: <itamar> clientTCP is in flux */
PyObject * cReactorTCP_connectTCP(PyObject *self, PyObject *args);

/* Apply a callable in the main thread. */
PyObject * cReactorThread_callFromThread(PyObject *self, PyObject *args, PyObject *kw);

/* Run a callable in another thread. */
PyObject * cReactorThread_callInThread(PyObject *self, PyObject *args, PyObject *kw);

/* Suggest the size of the thread pool. */
PyObject * cReactorThread_suggestThreadPoolSize(PyObject *self, PyObject *args);

/* Break the reactor out of poll. */
PyObject * cReactorThread_wakeUp(PyObject *self, PyObject *args);

PyObject * cReactorThread_initThreading(PyObject *self, PyObject *args);
void cReactorThread_freeThreadpool(cReactor *reactor);

/* Create a new APPLY job. */
cReactorJob * cReactorJob_NewApply(PyObject *callable, PyObject *args, PyObject *kw);

/* Create a new EXIT job. */
cReactorJob * cReactorJob_NewExit(void);

/* Destroy a previously created job. */
void cReactorJob_Destroy(cReactorJob *job);

/* Create a new job queue. */
cReactorJobQueue * cReactorJobQueue_New(void);

/* Destroy a previously created job queue. */
void cReactorJobQueue_Destroy(cReactorJobQueue *queue);

/* Add the given job to the queue.  This function assumes ownership over the
 * memory pointed to by 'job'.
 */
void cReactorJobQueue_AddJob(cReactorJobQueue *queue, cReactorJob *job);

/* Pop the top job off the queue and return it.  If there are no jobs this
 * returns NULL.
 */
cReactorJob * cReactorJobQueue_Pop(cReactorJobQueue *queue);

/* Same as cReactorJobQueue_Pop but waits until there is a job placed on the
 * queue.
 */
cReactorJob * cReactorJobQueue_PopWait(cReactorJobQueue *queue);

/* Set up the cDelayedCall module */
void cDelayedCall_init(void);
/* Set up cReactorTCP */
void cReactorTCP_init(void);

/* Create a cDelayedCall object. */
cDelayedCall * cDelayedCall_new(int delay_ms,
                                PyObject *callable,
                                PyObject *args,
                                PyObject *kw);

/* vim: set sts=4 sw=4: */
