package com.twistedmatrix.amp;

import com.twistedmatrix.internet.Protocol;

public abstract class Int16StringReceiver extends Protocol {

    byte[] recvd;

    static void cpy(byte[] a, byte[] b, int offt) {
        System.arraycopy(a, 0, b, offt, a.length);
    }
    static void cpy(byte[] a, byte[] b) {
        cpy(a, b, 0);
    }

    public Int16StringReceiver() {
        recvd = new byte[0];
    }

    public abstract void stringReceived(byte[] hunk);

    public void dataReceived(byte[] data) {
        byte[] old = recvd;
        recvd = new byte[old.length + data.length];

        cpy(old, recvd);
        cpy(data, recvd, old.length);

        while (tryToDeliverData()) {
            /* nothing to do */
        }
    }

    static int toInt(byte b) {
        // why doesn't java have unsigned bytes again?  at least python can
        // _emulate_ this easily.
        int i;
        if (b < 0) {
            i = 256 + (int) b;
        } else {
            i = (int) b;
        }
        return i;
    }

    /**
     * Attempt to drain some data from our buffer into somewhere else.
     */
    boolean tryToDeliverData() {
        if (recvd.length < 2) {
            return false;
        }

        /* unpack the 16-bit length */
        int reqlen = (toInt(recvd[0]) * 256) + toInt(recvd[1]);

        if (recvd.length < (2+reqlen)) {
            return false;
        }

        byte[] hunk = new byte[reqlen];
        System.arraycopy(recvd, 2, hunk, 0, reqlen);
        byte[] oldbuf = recvd;
        int newlen = oldbuf.length - reqlen - 2;
        recvd = new byte[newlen];
        System.arraycopy(oldbuf, reqlen + 2, recvd, 0, newlen);
        try {
            stringReceived(hunk);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return true;
    }
}
