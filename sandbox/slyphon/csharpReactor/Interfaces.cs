using System;
using System.Net;
using System.Net.Sockets;

namespace csharpReactor.interfaces {
	public interface ISocket {
		Socket socket { get; }
	}

	public interface IProducer {
		void stopProducing();
	}
	
	public interface IConsumer {
		void registerProducer(IProducer producer, bool streaming);
		void unregisterProducer();
		void write(String data);
	}

	// -- To be fleshed out later -----------------
	public interface IReadDescriptor : ISocket {}
	public interface IWriteDescriptor : ISocket {}
	public interface IReadWriteDescriptor : ISocket {}
	// ----------------------------------------

	
	/// <summary>
  /// A transport for bytes
  /// </summary>
  public interface ITransport : ISocket {
    IProtocol protocol { get; }
    IAddress client { get; }
    IPort server { get; }
    double sessionNum { get; }
    bool connected { get; }
    void startReading();
  }

  public interface IPort : ISocket {
    IPEndPoint localEndPoint { get; }
    int backlog { get; set; }
    IAddress address { get; }
    IFactory factory { get; set; }
    void doRead();
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
    IPort listenTCP(IPEndPoint ep, IFactory f, int backlog);
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
