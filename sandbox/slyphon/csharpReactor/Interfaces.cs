using System;
using System.Net;
using System.Net.Sockets;
using csharpReactor.misc;

namespace csharpReactor.interfaces {

  /// <summary>
  /// this is roughly equivalent to t.i.interfaces.ISystemHandle, but
  /// as Select() only works on WinSock sockets (grumble, grumble), 
  /// we can drop the charade and admit that we're only gonna be dealing
  /// with sockets.
  /// </summary>
  public interface ISocket {
    Socket socket { get; }
  }

  public interface IProducer {
    void stopProducing();
    void pauseProducing();
    void resumeProducing();
  }
	
  public interface IConsumer {
    void registerProducer(IProducer producer, bool streaming);
    void unregisterProducer();
    void write(String data);
  }

  // -- To be fleshed out later -----------------
  public interface IReadDescriptor : ISocket {
    void doRead();
  }

  public interface IWriteDescriptor : ISocket {
    Nullable<int> doWrite();
  }

  public interface IReadWriteDescriptor : IReadDescriptor, IWriteDescriptor {}
  // ----------------------------------------

	
  /// <summary>
  /// A transport for bytes
  /// 
  /// I represent (and wrap) the physical connection and synchronicity
  /// of the framework which is talking to the network.  I make no
  /// representations about whether calls to me will happen immediately
  /// or require returning to a control loop, or whether they will happen
  /// in the same or another thread.  Consider methods of this class
  /// (aside from getPeer) to be 'thrown over the wall', to happen at some
  /// indeterminate time
  /// </summary>
  public interface ITransport : ISocket {
    double sessionNum { get; }
    bool connected { get; }
	void write(String data);
	void writeSequence(String[] data);
	void loseConnection();
	/// <summary>
	/// returns an IAddress representing the other side of the connection
	/// it is not reliable (port forwarding, proxying, etc.)
	/// </summary>
	IAddress getPeer();
	/// <summary>
	/// returns an IAddress representing this side of the connection
	/// </summary>
	IAddress getHost();
  }

  public interface IListeningPort : ISocket {
    IPEndPoint localEndPoint { get; }
    IAddress address { get; }
    void startListening();
  }

  public interface IAddress {
    IPAddress ipAddress { get; set; }
    int port { get; set; }
    ProtocolType protocolType { get; set; }
  }

  public interface IConnectionLost {
    String reason {get; set;}
    Exception failure {get; set;}
  }

  public interface IReactor {
    IListeningPort listenTCP(IPEndPoint ep, IFactory f, int backlog);
    void doIteration(int timeout);
    void addReader(ISocket fd);
    void run();
    void stop();
    void mainLoop();
  }

  public interface IProtocol {
    IFactory factory { get; set; }
    bool connected { get; }
    ITransport transport { get; }

    /// <summary>
    /// called whenever data is received
    /// use this method to translate to a higher-level message. Usually, some
    /// callback will be made upon the receipt of each complete protocol message
    /// </summary>
    /// <param name="data">An ASCII-encoded translation of the bytes received 
    /// on the wire
    /// </param>
    void dataReceived(String data);
    void connectionLost(IConnectionLost reason);
    void makeConnection(ITransport t);
    void connectionMade();
  }
	
  public interface IFactory {
    IProtocol buildProtocol(IAddress addr);
    void doStart();
    void doStop();
  }
}
