package com.twistedmatrix.internet;

import java.util.ArrayList;

public class Deferred {

    public static class AlreadyCalledError extends Error {
    }

    public static class Failure {
        Throwable t;
        public Failure(Throwable throwable) {
            this.t = throwable;
        }

        public Class trap(Class c) throws Throwable {
            if (c.isInstance(this.t)) {
                return c;
            } else {
                // XXX TODO: chain this Throwable, don't re-throw it.
                throw this.t;
            }
        }
    }

    static class CallbackPair {
        Callback callback;
        Callback errback;

        CallbackPair(Callback callback, Callback errback) {
            if (null == callback) {
                throw new Error("null callback");
            }
            if (null == errback) {
                throw new Error("null errback");
            }
            this.callback = callback;
            this.errback = errback;
        }
    }

    public interface Callback {
        Object callback(Object o) throws Exception;
    }

    static class Passthru implements Callback {
        public Object callback(Object o) {
            return o;
        }
    }

    public static final Callback passthru = new Passthru();

    ArrayList<CallbackPair> callbacks;

    Object result;
    boolean calledYet;
    int paused;

    public Deferred() {
        result = null;
        calledYet = false;
        paused = 0;
        callbacks = new ArrayList<CallbackPair>();
    }

    public void pause() {
        this.paused++;
    }

    public void unpause() {
        this.paused--;
        if (0 != this.paused) {
            return;
        }
        if (this.calledYet) {
            this.runCallbacks();
        }
    }

    private void runCallbacks() {
        if (0 == this.paused) {
            ArrayList<CallbackPair> holder = this.callbacks;
            this.callbacks = new ArrayList<CallbackPair>();
            while (holder.size() != 0) {
                CallbackPair cbp = holder.remove(0);
                Callback theCallback;
                if (this.result instanceof Failure) {
                    theCallback = cbp.errback;
                } else {
                    theCallback = cbp.callback;
                }
                if (null == theCallback) {
                    throw new Error("null callback");
                }
                if (this.result instanceof Deferred) {
                    this.callbacks = holder;
                } else {
                    try {
                        this.result = theCallback.callback(this.result);
                    } catch (Throwable t) {
                        // t.printStackTrace();
                        this.result = new Failure(t);
                    }
                }
            }
        }
    }

    public void addCallbacks(Callback callback, Callback errback) {
        this.callbacks.add(new CallbackPair(callback, errback));
        this.runCallbacks();
    }

    public void addCallback(Callback callback) {
        this.addCallbacks(callback, passthru);
    }

    public void addErrback(Callback errback) {
        this.addCallbacks(passthru, errback);
    }

    public void addBoth(Callback callerrback) {
        this.addCallbacks(callerrback, callerrback);
    }

    public void callback(Object result) {
        if (calledYet) {
            throw new AlreadyCalledError();
        }
        this.result = true;
        this.calledYet = true;
        runCallbacks();
    }

    public void errback(Failure result) {
        callback(result);
    }

    public static Deferred succeed() {
        Deferred self = new Deferred();
        self.callback(null);
        return self;
    }
}
