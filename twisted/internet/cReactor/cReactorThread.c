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

/* includes */
#include "cReactor.h"
#include <signal.h>
#include <unistd.h>

static int cReactorThread_initThreadpool(cReactor *reactor);

/* The worker thread's main loop. */
static void *
worker_thread_main(void *arg)
{
    cReactorThread *thread;
    cReactorJob *job;
    PyThreadState *thread_state;
    PyThreadState *old_thread_state;
    PyObject *result;
    int done;
    sigset_t sigmask;

    /* Ignore ALL signals. */
    sigfillset(&sigmask);
    pthread_sigmask(SIG_SETMASK, &sigmask, NULL);

    /* Our argument is a cReactorThread pointer. */
    thread = (cReactorThread *)arg;

    /* Create a python thread state -- the intrepreter lock need not be held
     * for this.
     */
    thread_state = PyThreadState_New(thread->interp);

    /* The main loop. */
    done = 0;
    while (! done)
    {
        /* Wait for a job. */
        job = cReactorJobQueue_PopWait(thread->reactor->worker_queue);

        /* Do appropriate action. */
        switch (job->type)
        {
            case CREACTOR_JOB_APPLY:
                /* Acquire the global intrepreter lock. */
                PyEval_AcquireLock();

                /* Swap in our thread state for the active state. */
                old_thread_state = PyThreadState_Swap(thread_state);

                /* Run the callable. */
                result = PyEval_CallObjectWithKeywords(job->u.apply.callable,
                                                       job->u.apply.args,
                                                       job->u.apply.kw);
                Py_XDECREF(result);
                if (! result)
                {
                    PyErr_Print();
                }

                /* Destroy the job while we have the interpreter lock because
                 * this calls Py_DECREF!
                 */
                cReactorJob_Destroy(job);

                /* Restore the thread state. */
                PyThreadState_Swap(old_thread_state);

                /* Release the global interpreter lock. */
                PyEval_ReleaseLock();
                break;

            case CREACTOR_JOB_EXIT:
                done = 1;
                cReactorJob_Destroy(job);
                break;
        }
    }

    /* Destroy the thread state. */
    PyThreadState_Delete(thread_state);

    return NULL;
}


static void
wake_up_internal(cReactor *reactor)
{
    /* Write a byte to the control pipe.  This should be thread safe without
     * requiring a lock.
     */
    char byte;
    byte = 'W';
    write(reactor->ctrl_pipe, &byte, 1);
}


PyObject *
cReactorThread_callInThread(PyObject *self, PyObject *args, PyObject *kw)
{
    PyObject *req_args;
    PyObject *callable;
    cReactor *reactor;
    PyObject *callable_args;
    cReactorJob *job;

    reactor = (cReactor *)self;

    /* Split out the required args and parse them. */
    req_args = PyTuple_GetSlice(args, 0, 1);
    if (!PyArg_ParseTuple(req_args, "O:callInThread", &callable))
    {
        Py_DECREF(req_args);
        return NULL;
    }
    Py_DECREF(req_args);

    /* Verify that the object is a callable. */
    if (!PyCallable_Check(callable))
    {
        PyErr_SetString(PyExc_ValueError,
                        "callInThread arg 1 is not callable!");
        return NULL;
    }

    /* The threadpool must be initialized first. */
    if (!reactor->thread_pool) {
        if (cReactorThread_initThreadpool(reactor) != 0)
            return NULL;
    }

    /* Slice off the callable args. */
    callable_args = PyTuple_GetSlice(args, 1, PyTuple_Size(args));

    /* Create a new APPLY job. */
    job = cReactorJob_NewApply(callable, callable_args, kw);
    Py_DECREF(callable_args);

    /* Add it to the worker queue. */
    cReactorJobQueue_AddJob(reactor->worker_queue, job);

    Py_INCREF(Py_None);
    return Py_None;
}
    

PyObject *
cReactorThread_callFromThread(PyObject *self, PyObject *args, PyObject *kw)
{
    PyObject *req_args;
    PyObject *callable;
    cReactor *reactor;
    PyObject *callable_args;
    cReactorJob *job;
    
    reactor = (cReactor *)self;

    /* Split out the required args and parse them. */
    req_args = PyTuple_GetSlice(args, 0, 1);
    if (!PyArg_ParseTuple(req_args, "O:callFromThread", &callable))
    {
        Py_DECREF(req_args);
        return NULL;
    }
    Py_DECREF(req_args);

    /* Verify that the object is a callable. */
    if (!PyCallable_Check(callable))
    {
        PyErr_SetString(PyExc_ValueError, "callFromThread arg 1 is not callable!");
        return NULL;
    }

    /* The main thread (reactor) needs thread init to happen first. */
    if (! reactor->multithreaded)
    {
        PyErr_SetString(PyExc_RuntimeError,
                        "callFromThread received before initThreading!");
        return NULL;
    }

    /* Get the args for the callable. */
    callable_args = PyTuple_GetSlice(args, 1, PyTuple_Size(args));

    /* Make a new APPLY job. */
    job = cReactorJob_NewApply(callable, callable_args, kw);
    Py_DECREF(callable_args);

    /* Add it to the main thread's job queue. */
    cReactorJobQueue_AddJob(reactor->main_queue, job);

    /* Wake-up the reactor. */
    wake_up_internal(reactor);

    Py_INCREF(Py_None);
    return Py_None;
}


PyObject *
cReactorThread_wakeUp(PyObject *self, PyObject *args)
{
    cReactor *reactor;

    /* Args */
    if (!PyArg_ParseTuple(args, ":wakeUp"))
    {
        return NULL;
    }

    /* Do the wake up. */
    reactor = (cReactor *)self;
    wake_up_internal(reactor);

    Py_INCREF(Py_None);
    return Py_None;
}


PyObject *
cReactorThread_suggestThreadPoolSize(PyObject *self, PyObject *args)
{
    int pool_size;
    cReactor *reactor;

    reactor = (cReactor *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, "i:suggestThreadPoolSize", &pool_size))
    {
        return NULL;
    }

    /* Just set the size. */
    reactor->req_thread_pool_size = pool_size;

    /* TODO: if currently multithreaded, adjust the pool to this size. */

    Py_INCREF(Py_None);
    return Py_None;
}


PyObject *
cReactorThread_initThreading(PyObject *self, PyObject *args)
{
    /* This sets up main_queue, which is used to feed jobs to the main
       thread where they can be executed safely. runFromThread adds to this
       queue, and the main loop (iterate_internal) removes jobs from it.

       The queue set up by this function is never removed. */

    cReactor *reactor;

    reactor = (cReactor *)self;

    /* Args */
    if (!PyArg_ParseTuple(args, ":initThreading"))
    {
        return NULL;
    }

    /* Initialize the reactor's threadness. */
    if (! reactor->multithreaded)
    {
        /* Initialize python threads. */
        PyEval_InitThreads();

        /* We are now using threads. */
        reactor->multithreaded = 1;

        /* Make a thread safe job queue for the reactor. */
        reactor->main_queue = cReactorJobQueue_New();
    }

    Py_INCREF(Py_None);
    return Py_None;
}

/* 
   cReactorThread_initThreadpool:

   Set up the thread pool, used to process jobs dispatched by runInThread.
   This is run whenever runInThread notices that the pool is missing.

   The threads set up by this function are removed when the "shutdown" event
   trigger completes. This will occur when reactor.run() completes, either
   because .stop() was called, .crash() was called, or a signal was
   received.
*/

static int
cReactorThread_initThreadpool(cReactor *reactor)
{

    PyThreadState *thread_state;
    int i;
    cReactorThread *thread;

    if (reactor->thread_pool)
        return 0;

    /* Initialize the reactor's threadness. */
    if (!reactor->multithreaded)
    {
        PyObject *threadable_init, *obj;

        /* call threadable.init(1) */
        threadable_init = cReactorUtil_FromImport("twisted.python.threadable",
                                                  "init");
        if (!threadable_init)
            return -1;
        obj = PyObject_CallFunction(threadable_init, "(i)", 1);
        Py_DECREF(threadable_init);
        Py_XDECREF(obj);
        if (!obj)
            return -1;
        
        /* that will call cReactorThread_initThreading, which will set
           reactor->multithreaded */
        if (!reactor->multithreaded) {
            PyErr_SetString(PyExc_RuntimeError,
                            "initThreading failed to init threading");
        }
    }

    /* Make a worker queue. */
    reactor->worker_queue = cReactorJobQueue_New();

    /* Clamp the minimum thread pool size to 1. */
    if (reactor->req_thread_pool_size < 1)
    {
        reactor->req_thread_pool_size = 1;
    }

    /* Get the main thread's thread state. */
    thread_state = PyThreadState_Get();

    /* Create the threads. */
    for (i = 0; i < reactor->req_thread_pool_size; ++i)
    {
        thread = (cReactorThread *)malloc(sizeof(cReactorThread));
        if (!thread) {
            PyErr_SetString(PyExc_MemoryError,
                            "could not allocate a worker thread");
            return -1;
        }
        memset(thread, 0x00, sizeof(cReactorThread));

        /* Reactor link. */
        thread->reactor = reactor;

        /* The Interpreter state from the main thread. */
        thread->interp = thread_state->interp;

        /* Add it to the list. */
        thread->next            = reactor->thread_pool;
        reactor->thread_pool    = thread;

        /* Fire it up! */
        pthread_create(&thread->thread_id,
                       NULL,
                       worker_thread_main,
                       thread);
    }

    return 0;
}

void
cReactorThread_freeThreadpool(cReactor *reactor)
{
    cReactorThread *thread;
    PyThreadState *thread_state;

    /* No cleanup needed if we aren't using threads. */
    if (! reactor->multithreaded)
    {
        return;
    }

    /* Release the Python interpreter lock in case there are APPLY jobs still
     * in the worker queue.
     */
    thread_state = PyThreadState_Swap(NULL);
    PyEval_ReleaseLock();

    /* Issue EXIT jobs, one for each thread. */
    thread = reactor->thread_pool;
    while (thread)
    {
        cReactorJobQueue_AddJob(reactor->worker_queue, cReactorJob_NewExit());
        thread = thread->next;
    }

    /* Wait for them to finish. */
    thread = reactor->thread_pool;
    while (thread)
    {
        pthread_join(thread->thread_id, NULL);
        thread = thread->next;
    }

    /* Reacquire the lock. */
    PyEval_AcquireLock();
    PyThreadState_Swap(thread_state);
}


cReactorJob *
cReactorJob_NewApply(PyObject *callable, PyObject *args, PyObject *kw)
{
    cReactorJob *job;

    job = (cReactorJob *)malloc(sizeof(cReactorJob));
    memset(job, 0x00, sizeof(cReactorJob));

    job->type               = CREACTOR_JOB_APPLY;
    Py_INCREF(callable);
    job->u.apply.callable   = callable;
    Py_XINCREF(args);
    job->u.apply.args       = args;
    Py_XINCREF(kw);
    job->u.apply.kw         = kw;

    return job;
}


cReactorJob *
cReactorJob_NewExit(void)
{
    cReactorJob *job;

    job = (cReactorJob *)malloc(sizeof(cReactorJob));
    memset(job, 0x00, sizeof(cReactorJob));

    job->type = CREACTOR_JOB_EXIT;
    return job;
}

void
cReactorJob_Destroy(cReactorJob *job)
{
    switch (job->type)
    {
        case CREACTOR_JOB_APPLY:
            Py_DECREF(job->u.apply.callable);
            Py_XDECREF(job->u.apply.args);
            Py_XDECREF(job->u.apply.kw);
            break;

        case CREACTOR_JOB_EXIT:
            /* Nothing to do. */
            break;
    }

    free(job);
}

cReactorJobQueue *
cReactorJobQueue_New(void)
{
    cReactorJobQueue *queue;

    queue = (cReactorJobQueue *)malloc(sizeof(cReactorJobQueue));
    pthread_mutex_init(&queue->lock, NULL);
    pthread_cond_init(&queue->cond, NULL);
    queue->jobs = NULL;

    return queue;
}


void
cReactorJobQueue_Destroy(cReactorJobQueue *queue)
{
    if (queue)
    {
        /* TODO: error check? */
        pthread_mutex_destroy(&queue->lock);
        pthread_cond_destroy(&queue->cond);
        free(queue);
    }
}


void
cReactorJobQueue_AddJob(cReactorJobQueue *queue, cReactorJob *job)
{
    cReactorJob *search;

    /* Acquire the lock. */
    pthread_mutex_lock(&queue->lock);

    search = queue->jobs;
    if (search)
    {
        /* Add to the end. */
        while (search->next)
        {
            search = search->next;
        }
        search->next    = job;
        job->next       = NULL;
    }
    else
    {
        /* First job. */
        queue->jobs     = job;
        job->next       = NULL;
    }

    /* Signal the condition var. */
    pthread_cond_signal(&queue->cond);

    /* Unlock. */
    pthread_mutex_unlock(&queue->lock);
}


cReactorJob *
cReactorJobQueue_Pop(cReactorJobQueue *queue)
{
    cReactorJob *job = NULL;

    /* Acquire the lock. */
    pthread_mutex_lock(&queue->lock);

    if (queue->jobs)
    {
        job             = queue->jobs;
        queue->jobs     = job->next;
        job->next       = NULL;
    }

    /* Unlock */
    pthread_mutex_unlock(&queue->lock);

    return job;
}


cReactorJob *
cReactorJobQueue_PopWait(cReactorJobQueue *queue)
{
    cReactorJob *job = NULL;

    /* Acquire the lock. */
    pthread_mutex_lock(&queue->lock);

    while (! job)
    {
        /* If the job list is empty wait for a signal. */
        if (! queue->jobs)
        {
            pthread_cond_wait(&queue->cond, &queue->lock);
        }

        /* Pop it. */
        if (queue->jobs)
        {
            job             = queue->jobs;
            queue->jobs     = job->next;
            job->next       = NULL;
        }
    }

    /* Unlock */
    pthread_mutex_unlock(&queue->lock);

    return job;
}


/* vim: set sts=4 sw=4: */
