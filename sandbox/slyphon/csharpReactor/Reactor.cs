using System;
using System.Net;
using System.Net.Sockets;
using System.Collections;
using csharpReactor.Collections;

namespace csharpReactor {
	/// <summary>
	/// Summary description for Reactor.
	/// </summary>
	public class Reactor : IReactor {
		private SocketConnectorDict readers = new SocketConnectorDict();
		private SocketConnectorDict writers = new SocketConnectorDict();
		private ArrayList ignore = new ArrayList();
		private bool running = false;
		
		public void ListenTCP(IPEndPoint endPoint, IFactory factory, int backlog) {
			Socket listener = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
			listener.Bind(endPoint);
			listener.Listen(backlog);
			Connector cnx = new Connector(listener, factory, 20, this);
			readers.Add(cnx.SockHandle, cnx);
		}
		
		public void DoSelect(int timeout){
			Socket[] reads = new Socket[readers.Keys.Count];
			readers.Keys.CopyTo(reads, 0);
			Socket[] writes = new Socket[writers.Keys.Count];
			writers.Keys.CopyTo(writes, 0);

			while (true) {
				try {
					Socket.Select(reads, writes, null, timeout);
					break;
				} catch (ArgumentNullException e) {
					Console.WriteLine("argument null exception: " + e.StackTrace);
				} catch (SocketException e) {
					Console.WriteLine("SocketException caught " + e.StackTrace);
					continue;
				}
			}
			if (reads.Length > 0) {
				foreach (Socket s in reads) {
					Console.WriteLine("Socket " + s + " is readable");
				}
			}
		}
			
		public void Run() {
			this.running = true;
			MainLoop();
		}

		public void Stop() {
			this.running = false;
		}

		public void MainLoop() {
			Console.WriteLine("MainLoop running");
			while (this.running) {
				this.DoSelect(100);
			}
		}

		public static void Main() { 
			Reactor r = new Reactor();
			r.ListenTCP(new IPEndPoint(IPAddress.Parse("127.0.0.1"), 9999), new Factory(), 10);
			r.Run();
		}
	}
}
