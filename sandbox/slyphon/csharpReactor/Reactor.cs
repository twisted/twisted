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
		private Hashtable reads = new Hashtable();
		private Hashtable writes = new Hashtable();
		private bool running = false;
		
		public Port listenTCP(IPEndPoint endPoint, IFactory factory, int backlog) {
			Port p = new Port(endPoint, factory, backlog, this);
			p.startListening();
			return p;
		}

		public void doSelect(int timeout) {
			ArrayList readers = new ArrayList(reads.Keys);
			ArrayList writers = new ArrayList(writes.Keys);

			Socket.Select(readers, writers, null, timeout);
			if (readers.Count > 0) {
				Console.WriteLine("we got a connectable socket!");
			}
		}
		
		public void addReader(IFileDescriptor fd) {
			this.reads.Add(fd.selectableSocket, fd);
		}
			
		public void run() {
			this.running = true;
			mainLoop();
		}

		public void stop() {
			this.running = false;
		}

		public void mainLoop() {
			Console.WriteLine("MainLoop running");
			while (this.running) {
				this.doSelect(100);
			}
		}

		public static void Main() { 
			Reactor r = new Reactor();
			r.listenTCP(new IPEndPoint(IPAddress.Parse("127.0.0.1"), 9999), new Factory(), 10);
			r.run();
		}
	}
}
