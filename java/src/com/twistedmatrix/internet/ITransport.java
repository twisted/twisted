
package com.twistedmatrix.internet;

public interface ITransport {
    void write(byte[] data);
    // no reason for writeSequence; it's unclear we'd be able to get any
    // boost.
    void loseConnection();

    // probably need this soon

    // void getPeer();
    // void getHost();
}