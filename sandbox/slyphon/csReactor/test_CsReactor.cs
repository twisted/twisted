using System;
using System.Net.Sockets;

namespace CSReactor
{
	using NUnit.Framework;

	/// <summary>
	/// Summary description for test_CsReactor.
	/// </summary>
	[TestFixture]
	public class test_CsReactor
	{
		[Test]
		public void TestAddReader(){
			MonoReactor mr = new MonoReactor();
			Socket s = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
			
		}
	}
}
