using System;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Collections;

namespace CSReactor {
  /// <summary>
  /// Summary description for SimpleClientServer.
  /// </summary>
  public interface IConnectionLost {
    String reason {get; set;}
    Exception failure {get; set;}
  }

  public interface IReactor {}

  public interface IProtocol {
    IFactory Factory { get; set; }
    bool Connected { get; }
    void dataReceived(String data);
    void connectionLost(IConnectionLost reason);
    void makeConnection();
    void connectionMade();
  }
	
  public interface IFactory {
    IProtocol buildProtocol();
    void doStart();
    void doStop();
  }

  public class BaseProtocol {
    protected bool connected = false;
    protected IFactory factory;
    protected IPEndPoint address = null;
		
    public BaseProtocol() : this(null, null) {}

    public BaseProtocol(IPEndPoint address) : this(address, null) {
    }

    public BaseProtocol(IPEndPoint address, IFactory factory) {
      this.address = address;
      this.factory = factory;
    }

    public bool Connected {
      get { return this.connected; }
    }
		
    public IFactory Factory {
      get { return this.factory; }
      set { this.factory = value; }
    }

    public virtual void makeConnection() {
      this.connected = true;
      this.connectionMade();
    }

    public virtual void connectionMade() {}
  }

  public class Protocol : BaseProtocol, IProtocol {
    public virtual void connectionLost(IConnectionLost reason) {}
    public virtual void dataReceived(String data) {}
  }

  public class Factory : IFactory {
    protected Type protocol;

    public System.Type Protocol {
      get { return this.protocol; }
      set { this.protocol = value; }
    }

    public virtual void doStart() {}
    public virtual void doStop() {}
    public virtual IProtocol buildProtocol() {
      return (IProtocol)System.Activator.CreateInstance(this.protocol);
    }
  }
	
  public class BaseConnector {
    protected IFactory factory;
    protected int timeout;
    protected IReactor reactor;
    protected Socket sock;
    protected IProtocol protocol;
    private static int BUF_SIZE = 8192;
    private byte[] readBuffer = new byte[BUF_SIZE];

    public Socket SockHandle {
      get { return this.sock; }
    }

    public IPEndPoint BindAddress {
      get { return (IPEndPoint)sock.LocalEndPoint; }
    }

    public IPEndPoint Peer {
      get { return (IPEndPoint)sock.RemoteEndPoint; }
    }

    public BaseConnector(IFactory factory, int timeout, IReactor reactor) {
      this.factory = factory;
      this.timeout = timeout;
      this.reactor = reactor;
    }
    
    private IAsyncResult SetupRead() {
      for (int i=0; i < readBuffer.Length; i++) {
        readBuffer[i] = 0;
      }
      return sock.BeginReceive(this.readBuffer, 0, BUF_SIZE, SocketFlags.None,
        new AsyncCallback(this.DoRead), this);
    }

    public void DoRead(IAsyncResult ar) {
      sock.EndReceive(ar);
      StringBuilder sb = new StringBuilder(BUF_SIZE);
      for (int i=0; i < readBuffer.Length; i++) {
        sb.Append(Convert.ToChar(sb[i]));
      }
      protocol.dataReceived(sb.ToString());
      SetupRead();
    }

    public void DoConnect(IAsyncResult ar) {
      Socket listener = (Socket)ar.AsyncState;
      Socket sock = listener.EndAccept(ar);
      protocol = (IProtocol) factory.buildProtocol();
      SetupRead();
    }  
  }

  public class TwistedServer : IReactor {
    private ArrayList listeners = new ArrayList(); 
    private bool running = false;

    public IAsyncResult ListenTCP(IPEndPoint endPoint, IFactory factory, int backlog){
      Socket listener = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
      listener.Bind(endPoint);
      listener.Listen(backlog);
      BaseConnector cnx = new BaseConnector(factory,20, this);
      listeners.Add(cnx);
      return listener.BeginAccept(new AsyncCallback(cnx.DoConnect), listener);
    }	

    public void Run() {
      this.running = true;  
      MainLoop();
    }

    public void Stop() {
      this.running = false;
    }

    protected void MainLoop() {
      Console.WriteLine("MainLoop running");
      while (this.running) {}
    }
  }
}
