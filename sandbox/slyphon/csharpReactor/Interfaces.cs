using System;
using System.Net;
using System.Net.Sockets;

namespace csharpReactor.interfaces {
  /// <summary>
  /// A transport for bytes
  /// </summary>
  public interface ITransport {
    Socket socket { get; }
    IProtocol protocol { get; }
    IAddress client { get; }
    IPort server { get; }
    double sessionNum { get; }
    bool connected { get; }
    void startReading();
  }

  public interface IPort {
    IPEndPoint localEndPoint { get; }
    int backlog { get; set; }
    Socket selectableSocket { get; }
    IAddress address { get; }
    bool connected { get; }
    double sessionNum { get; }
    IFactory factory { get; set; }
    void doRead();
    void startReading();
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
    void addReader(IFileDescriptor fd);
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
  
  public interface IFileDescriptor {
    /// <summary>
    /// start waiting for read availability
    /// </summary>
    void startReading();
    Socket selectableSocket { get; }
  }
}
