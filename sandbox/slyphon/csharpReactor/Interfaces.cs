using System;

namespace csharpReactor {
	public interface IConnectionLost {
		String reason {get; set;}
		Exception failure {get; set;}
	}

	public interface IReactor {}

	public interface IProtocol {
		IFactory Factory { get; set; }
		bool Connected { get; }
		void dataReceived(String data);
		void connectionLost(IConnectionLost reason);
		void makeConnection();
		void connectionMade();
	}
	
	public interface IFactory {
		IProtocol buildProtocol();
		void doStart();
		void doStop();
	}
  
	public interface IConnector {}

}
