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
      public override IProtocol buildProtocol(IPEndPoint addr, IFactory fact) {
        return (IProtocol) new BogusProtocol(addr, fact);
      }
    }

    [TestFixture]
    public class TestProtocol {
      public static IPAddress localhost = IPAddress.Parse("127.0.0.1");
      public static IPEndPoint endpoint = new IPEndPoint(localhost, 0);

      public void testBaseProtocol() {
        BogusProtocol bp = new BogusProtocol();
        Transport t = new Transport();
        bp.makeConnection(t);
        Assert.AreSame(bp.Transport, t);
        Assert.IsTrue(bp.Connected);
        Assert.IsTrue(bp.cnxMadeCalled);
      }
      
      public void testFactory() {
        Factory f = new Factory();
        IProtocol p = (IProtocol)f.buildProtocol(endpoint, f);
        Assert.AreSame(p.Factory, f);
      }
    }
  }
}
