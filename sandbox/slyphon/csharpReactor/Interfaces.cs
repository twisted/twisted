using System;
using System.Net;
using System.Net.Sockets;

namespace csharpReactor {
	/// <summary>
	/// A transport for bytes
	/// </summary>
	public interface ITransport {
		void startReading();
	}

	public interface IPort {
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
		void addReader(IFileDescriptor fd);
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
