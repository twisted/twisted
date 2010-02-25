HTTP11ClientProtocol now has an abort() method for cancelling an outstanding
request by closing the connection before receiving the entire response.
