twisted.web.wsgi now exposes new seek metod in class _InputStream

The new seek method in class _InputStream (twisted.web.wsgi) allows you to move the position in the stream allowing you to skip part of the stream or read the stream or (parts of) more than once.