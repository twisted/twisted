using System;
using System.Net;
using System.Net.Sockets;
using csharpReactor.interfaces;

namespace csharpReactor.tcp {
  public class Server : ITransport, ISocket {
    protected Socket _sock;
    protected IProtocol _protocol;
    protected IAddress _client;
    protected IPort _server;
    protected double _sessionNum;
    protected bool _connected = false;
    
		public Socket socket {
			get { return this._sock; }
		}

    public IProtocol protocol {
      get { return this._protocol; }
    }
    
    public IAddress client {
      get { return this._client; }
    }

    public IPort server { 
      get { return this._server; }
    }

    public double sessionNum {
      get { return this._sessionNum; }
    }

    public bool connected {
      get { return this._connected; }
    }

    public Server(Socket sock, IProtocol p, IAddress client, IPort server, double sessionNum) {
      this._sock = sock;
      this._protocol = p;
      this._client = client;
      this._server = server;
      this._sessionNum = sessionNum;
      // TODO: figure out logging code at some point and put default logstr here
      startReading();
      this._connected = true;
    }

    public void startReading() {
			Reactor.instance.addReader((ISocket)this);
    }
  }


  public class Port : existential.FileDescriptor, IPort {
    public static AddressFamily addressFamily = AddressFamily.InterNetwork;
    public static SocketType socketType = SocketType.Stream;
    public static ProtocolType protocolType = ProtocolType.Tcp;
    protected IPEndPoint _localEndPoint;
    protected IFactory _factory;
    protected int _backlog;
    protected IAddress _address;
    protected int _numberAccepts = 100;
    protected IReactor _reactor;


    // -- Property Definitions --------------

    public IPEndPoint localEndPoint {
      get { return this._localEndPoint; }
    }

    public IFactory factory {
      get { return this._factory; }
			set { this._factory = value; }
    }

    public int backlog {
      get { return this._backlog; }
      set { this._backlog = value; }
    }

    public IAddress address {
      get { return this._address; }
    }
    
    public IReactor reactor {
      get { return this._reactor; }
    }


    /// <summary>
    /// I am a TCP server port, listening for connections
    /// </summary>
    /// <param name="_localEndPoint">the local end point to bind to</param>
    /// <param name="factory">the IFactory object I will use to create protocol instances with</param>
    /// <param name="backlog">number of backlogged connections to keep queued</param>
    /// <param name="reactor"></param>
    public Port(IPEndPoint localEndPoint, IFactory factory, int backlog, IReactor reactor) { // not sure how to handle "interface" on win32
      this._localEndPoint = localEndPoint;
      this._factory = factory;
      this._backlog = backlog;
      this._reactor = reactor;
      this._address = new Address(protocolType, localEndPoint);
    }

    /// <summary>
    /// called when my socket is ready for reading!
    /// accept a connection and sets up the protocol
    /// </summary>
    public virtual void doRead() {
      Socket s = this._socket.Accept();
      IProtocol p = this._factory.buildProtocol(new Address(s));
      if (p == null) {
        s.Close(); // reject the connection attempt
      } else {
        this._sessionNum++; // XXX: Should probably be concerned about rollover
        ITransport transport = new Server(s, p, new Address(s), (IPort)this, this._sessionNum);
        p.makeConnection(transport);
      }
    }

    protected Socket createInternetSocket() {
      Socket s = new Socket(addressFamily, socketType, protocolType);
      s.Blocking = false;
      this._socket = s;
      return s;
    }

    /// <summary>
    /// Create and bind my socket, and begin listening on it
    /// </summary>
    public virtual void startListening() {
      Socket skt = createInternetSocket();
      skt.Bind(_localEndPoint);
      this._factory.doStart();
      skt.Listen(_backlog);
      this._connected = true;
      this._socket = skt;
      startReading();
    }
  }
}
