using System;
using System.Collections;
using System.Net.Sockets;

namespace CSReactor {
	class Reactor {
		public int backlog = 10;
		// public static int MAX_SOCKETS = 1024;
		SortedList rsock = new SortedList();
		SortedList wsock = new SortedList();
                
		public void doSelect(System.Int32 timeout) {
		}

		public void addReader(Socket s) {
			reads.Add(s, 1);
		}
        
		public void addWriter(Socket s) {
			writes.Add(s, 1);
		}

		public void removeReader(Socket s) {
			if (reads.ContainsKey(s)) {
				reads.Remove(s);
			}
		}
        
		public void removeWriter(Socket s) {
			if (writes.ContainsKey(s)) {
				writes.Remove(s);
			}
		}

#if false       
		public SortedList removeAll() {
			SortedList readers = (SortedList)rsock.Copy();
			foreach (Socket s in readers) {
				if (reads.ContainsKey(s)) {
					reads.Remove(s);
				}
				if (writes.ContainsKey(s)) {
					writes.Remove(s);
				}
			}
			return readers;
		}
#endif

		public void ListenTCP(String addr, int port) {
			Socket listenfd = new Socket(AddressFamily.InterNetwork, 
				SocketType.Stream, ProtocolType.Tcp);
			Console.WriteLine("created socket, binding");
			listenfd.Bind(new IPEndPoint(IPAddress.Parse(addr), port));
			Console.WriteLine("listening");
			listenfd.Listen(this.backlog);
			listenfd.Blocking = true;
			rsock.Add(listenfd, 1);
		}

		public void MainLoop() {
			this.running = true;
			while (this.running) {
				try {
					DoIteration();	
				} catch (Exception e) {
					Console.WriteLine("MainLoop caught exception:\n{0}", e.StackTrace);
				}
			}
		}

		public void DoIteration(int timeout) {
			ArrayList reads = ((ArrayList)rsock.GetKeyList()).Clone();
			ArrayList writes = ((ArrayList)wsock.GetKeyList()).Clone();
			ArrayList ignore = new ArrayList();
			while (true) {
				try {
					Socket.Select(reads, writes, ignore, timeout);
					break;
				} catch (ArgumentNullException e) {
					Console.Write(".", e.ToString());
				} catch (SocketException e) {
					Console.WriteLine("caught SocketException, something is fucked up!: " + e.ToString());
				}
			}
			if (reads.Count != 0) {
				Console.WriteLine("got a read");
				foreach (Socket s in reads) {
					byte[] bytes = new byte[1024];
					try {
						s.Receive(bytes);
					} catch (Exception e) {
						Console.WriteLine("exception caught: ", e.ToString());
					}	 
					Console.WriteLine(Encoding.ASCII.GetString(bytes));
				}
			} 
		}

		public void DoIteration() {
			this.DoIteration(0);
		}

		[STAThread]
		static void Main(string[] args) {
			//
			// TODO: Add code to start application here
			//
		}
	}
}
