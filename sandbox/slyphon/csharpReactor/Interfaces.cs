using System;
using System.Net.Sockets;
namespace csharpReactor {
	public interface IConnectionLost {
		String reason {get; set;}
		Exception failure {get; set;}
	}

	public interface IReactor {
		void AddReader(IFileDescriptor fd);
	}

	public interface IProtocol {
		IFactory Factory { get; set; }
		bool Connected { get; }
		void DataReceived(String data);
		void ConnectionLost(IConnectionLost reason);
		void MakeConnection();
		void ConnectionMade();
	}
	
	public interface IFactory {
		IProtocol BuildProtocol();
		void DoStart();
		void DoStop();
	}
  
	public interface IFileDescriptor {
		/// <summary>
		/// start waiting for read availability
		/// </summary>
		void StartReading();
		Socket SelectableSocket { get; }
	}
}
