using System;
using System.Net;
using System.Net.Sockets;
using NMock;
using NUnit.Framework;

namespace CSReactor {
  namespace Test {
    public class BogusProtocol : BaseProtocol {
      public bool cnxMadeCalled = false;
      
      public BogusProtocol() : base() {}
      public BogusProtocol(IPEndPoint addr, IFactory factory) : base(addr, factory) {} 

      public override void connectionMade() {
        this.cnxMadeCalled = true;
      }
    }
    public class BogusFactory : Factory {
    }

    [TestFixture]
    public class TestProtocol {
      public static IPAddress localhost = IPAddress.Parse("127.0.0.1");
      public static IPEndPoint endpoint = new IPEndPoint(localhost, 0);

      public void testBaseProtocol() {

      }
      
      public void testFactory() {

      }
    }


    
    public class SimpleProtocol : Protocol {
      public override void dataReceived(String data) {
        Console.WriteLine("received: " + data);
      }
    }
    
    public class AFactory : Factory {
      public AFactory() {
        this.protocol = typeof(SimpleProtocol);
      }
    }

    public class Tryitout {
      public static void Main() {
        IPEndPoint ep = new IPEndPoint(IPAddress.Parse("127.0.0.1"), 9999);
        AFactory af = new AFactory();
        TwistedServer ts = new TwistedServer();
        ts.ListenTCP(ep, af, 19);
        ts.Run();
      }
    }
  }
}
