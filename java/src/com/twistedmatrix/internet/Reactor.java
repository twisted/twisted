
package com.twistedmatrix.internet;

import java.util.ArrayList;
import java.util.TreeMap;
import java.util.Iterator;
import java.util.NoSuchElementException;
import java.io.IOException;

import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;

import java.nio.ByteBuffer;

import java.nio.channels.Selector;
import java.nio.channels.ClosedChannelException;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.nio.channels.SelectionKey;

public class Reactor {

    static int BUFFER_SIZE = 8 * 1024;

    public static Reactor get() {
        if (theReactor == null) {
            try {
                theReactor = new Reactor();
            } catch (Throwable t) {
                t.printStackTrace();
            }
        }
        return theReactor;
    }

    static Reactor theReactor;

    public interface IListeningPort {
        void stopListening();
    }

    /* It appears that this interface is actually unnamed in
     * Twisted... abstract.FileDescriptor serves this purpose.
     */
    class Selectable {
        SelectionKey sk;

        void doRead() throws Throwable {
            msg("UNHANDLED READ "+this);
        }
        void doWrite() throws Throwable {
            msg("UNHANDLED WRITE "+this);
        }

        // and we don't need this, because there's no such thing as
        // "acceptable" outside the magical fantasyland where Java lives.
        void doAccept() throws Throwable {
            msg("UNHANDLED ACCEPT "+this);
        }
        void doConnect() throws Throwable {
            msg("UNHANDLED CONNECT "+this);
        }
    }

    public class TCPPort extends Selectable implements IListeningPort {
        IProtocol.IFactory protocolFactory;
        ServerSocketChannel ssc;
        ServerSocket ss;
        InetSocketAddress addr;

        TCPPort(int portno, IProtocol.IFactory pf) throws IOException {
            this.protocolFactory = pf;
            this.ssc = ServerSocketChannel.open();
            this.ssc.configureBlocking(false);
            this.ss = ssc.socket();
            this.addr = new InetSocketAddress(portno);
            this.ss.bind(this.addr);
            this.startListening();
        }

        public void startListening() throws ClosedChannelException {
            this.sk = ssc.register(selector, SelectionKey.OP_ACCEPT, this);
        }

        public void stopListening() {
            /// ???
            this.sk.cancel();
        }

        public void doAccept() throws Throwable {
            SocketChannel newsc = ssc.accept();
            if (null == newsc) {
                return;
            }
            newsc.configureBlocking(false);
            Socket socket = newsc.socket();

            IProtocol p = this.protocolFactory.buildProtocol(this.addr);
            new TCPServer(p, newsc, socket);
        }
    }

    abstract class TCPConnection extends Selectable implements ITransport {
        ByteBuffer inbuf;
        ArrayList<byte[]> outbufs;

        IProtocol protocol;
        SocketChannel channel;
        Socket socket;
        SelectionKey sk;

        boolean disconnecting;

        TCPConnection(IProtocol protocol, SocketChannel channel, Socket socket) throws Throwable {
            inbuf = ByteBuffer.allocate(BUFFER_SIZE);
            inbuf.clear();
            outbufs = new ArrayList<byte[]>();
            this.protocol = protocol;
            this.channel = channel;
            this.socket = socket;
            this.disconnecting = false;
            this.sk = channel.register(selector, SelectionKey.OP_READ, this);
            this.protocol.makeConnection(this);
        }

        // HAHAHAHA the fab four strike again
        void startReading() {
            sk.interestOps(sk.interestOps() | SelectionKey.OP_READ);
        }

        void startWriting () {
            sk.interestOps(sk.interestOps() | SelectionKey.OP_WRITE);
        }

        void stopReading () {
            sk.interestOps(sk.interestOps() & ~SelectionKey.OP_READ);
        }

        void stopWriting () {
            sk.interestOps(sk.interestOps() & ~SelectionKey.OP_WRITE);
        }

        void doRead() throws Throwable {
            boolean failed = false;
            Throwable reason = null;
            try {
                int bytesread = channel.read(inbuf);
                failed = (-1 == bytesread);
            } catch (IOException ioe) {
                failed = true;
                reason = ioe;
            }

            if (failed) {
                // this means the connection is closed, what???
                channel.close();
                sk.cancel();
                this.protocol.connectionLost(reason);
                return;
            }

            byte[] data = new byte[inbuf.position()];
            inbuf.flip();
            inbuf.get(data);
            inbuf.clear();
            try {
                this.protocol.dataReceived(data);
            } catch (Throwable t) {
                t.printStackTrace();
                this.loseConnection();
            }
        }

        public void write(byte[] data) {
            this.outbufs.add(data);
            this.startWriting();
        }

        void doWrite() throws Throwable {
            /* XXX TODO: this cannot possibly be correct, but every example
             * and every tutorial does this!  Insane.
             */
            if (0 == this.outbufs.size()) {
                if (this.disconnecting) {
                    this.channel.close();
                }
                // else wtf?
            } else {
                this.channel.write(ByteBuffer.wrap(this.outbufs.remove(0)));
                if (0 == this.outbufs.size()) {
                    this.stopWriting();
                }
            }
        }

        public void loseConnection() {
            this.disconnecting = true;
        }
    }
    class TCPServer extends TCPConnection {
        // is there really any need for this to be a separate class?
        public TCPServer(IProtocol a, SocketChannel b, Socket c) throws Throwable {
            super(a, b, c);
        }
    }

    Selector selector;
    boolean running;
    TreeMap<Long,Runnable> pendingCalls;

    Reactor () throws Throwable {
        this.selector = Selector.open();
        this.running = false;
        this.pendingCalls = new TreeMap<Long,Runnable>();
    }

    public interface IDelayedCall {
        void cancel ();
    }

    public void callLater(double secondsLater, Runnable runme) {
        long millisLater = (long) (secondsLater * 1000.0);
        pendingCalls.put(System.currentTimeMillis() + millisLater,
                         runme);
    }

    /**
     * Run all runnables scheduled to run before right now, and return the
     * timeout.  Negative timeout means "no timeout".
     */
    long runUntilCurrent(long now) {
        while (0 != pendingCalls.size()) {
            try {
                long then = pendingCalls.firstKey();
                if (then < now) {
                    Runnable r = pendingCalls.remove((Object) new Long(then));
                    r.run();
                } else {
                    return then - now;
                }
            } catch (NoSuchElementException nsee) {
                nsee.printStackTrace();
                throw new Error("This is impossible; pendingCalls.size was not zero");
            }
        }
        return -1;
    }

    public void run() throws Throwable {
        running = true;
        while (running) {
            long now = System.currentTimeMillis();
            int selected;
            long timeout = runUntilCurrent(now);
            if (timeout >= 0) {
                selector.select(timeout);
            } else {
                selector.select();
            }
            Iterator<SelectionKey> selectedKeys = this.selector.selectedKeys().iterator();
            while(selectedKeys.hasNext()) {
                SelectionKey sk = selectedKeys.next();
                selectedKeys.remove();

                Selectable selectable = ((Selectable) sk.attachment());
                if (sk.isValid() && sk.isWritable()) {
                    selectable.doWrite();
                }
                if (sk.isValid() && sk.isReadable()) {
                    selectable.doRead();
                }
                if (sk.isValid() && sk.isAcceptable()) {
                    selectable.doAccept();
                }
                if (sk.isValid() && sk.isConnectable()) {
                    selectable.doConnect();
                }
            }
        }
    }

    public void stop() {
        this.running = false;
    }

    public IListeningPort listenTCP(int portno,
                                    IProtocol.IFactory factory)
        throws IOException {
        return new TCPPort(portno, factory);
    }

    public static void msg (String m) {
        System.out.println(m);
    }

    static class ShowMessage implements Runnable {
        String x;
        ShowMessage(String s) {
            this.x = s;
        }
        public void run () {
            msg(System.currentTimeMillis() + " " + this.x);
        }
    }

    public static void main (String[] args) throws Throwable {
        // The most basic server possible.
        Reactor r = Reactor.get();

        r.callLater(1, new ShowMessage("one!"));
        r.callLater(3, new ShowMessage("three!"));
        r.callLater(2, new ShowMessage("two!"));
        r.callLater(4, new ShowMessage("four!"));

        r.listenTCP(1234, new IProtocol.IFactory() {
                public IProtocol buildProtocol(Object addr) {
                    return new Protocol() {
                        public void dataReceived(byte[] data) {
                            this.transport().write(data);
                            Reactor.get().callLater(1, new ShowMessage("some data, delayed: " + new String(data)));
                        }
                    };
                }
            });
        r.run();
    }
}