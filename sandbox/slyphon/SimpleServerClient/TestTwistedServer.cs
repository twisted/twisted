using System;
using NMock;
using NUnit.Framework;

namespace CSReactor {
	namespace Test {
		public class BogusProtocol : BaseProtocol {
			public bool cnxMadeCalled = false;
			public override void connectionMade() {
				this.cnxMadeCalled = true;
			}
		}
		[TestFixture]
		public class TestProtocol {
			public void testBaseProtocol() {
				BogusProtocol bp = new BogusProtocol();
				BaseTransport bt = new BaseTransport();
				bp.makeConnection(bt);
				Assert.AreSame(bp.Transport, bt);
				Assert.IsTrue(bp.Connected);
				Assert.IsTrue(bp.cnxMadeCalled);
			}
			public void testFactory() {
				
			}
		}
	}
}