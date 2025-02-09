from websocket_server import WebsocketServer, WebSocketHandler, StreamRequestHandler
from socketserver import TCPServer
from flask import Flask
from io import BytesIO
import threading
import logging
import sys
import ssl

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(name)s/%(levelname)s]: %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger("FloraServer")
logger.propagate = True
logger.setLevel(logging.INFO)


class FloraWebSocketHandler(WebSocketHandler):
    def read_http_headers(self):
        headers = {}
        http_get = self.rfile.readline().decode().strip()
        if not http_get.upper().startswith("GET"):
            logger.warning("The client used an incorrect HTTP method to request WebSocket communication")
            response = "HTTP/1.1 400 Bad Request\r\n\r\n"
            with self._send_lock:
                self.request.sendall(response.encode())
            self.keep_alive = False
            return headers
        while True:
            header = self.rfile.readline().decode().strip()
            if not header:
                break
            head, value = header.split(":", 1)
            headers[head.lower().strip()] = value.strip()
        return headers

    def handshake(self):
        headers = self.read_http_headers()
        if "upgrade" in headers:
            try:
                assert headers.get("upgrade").lower() == "websocket"
            except AssertionError:
                self.keep_alive = False
                return
            try:
                key = headers.get("sec-websocket-key")
            except KeyError:
                logger.warning("The client attempted to connect, but the Sec-WebSocket-Key is missing")
                self.keep_alive = False
                return
            response = self.make_handshake_response(key)
            with self._send_lock:
                self.handshake_done = self.request.send(response.encode())
            self.valid_client = True
            self.server._new_client_(self)
        else:
            logger.warning("The client used an incorrect WebSocket protocol for communication")
            response = "HTTP/1.1 400 Bad Request\r\n\r\n"
            with self._send_lock:
                self.request.sendall(response.encode())
            self.keep_alive = False


class FloraWebsocketServer(WebsocketServer):
    def __init__(self, host="127.0.0.1", port=3000, loglevel=logging.WARNING, key=None, cert=None):
        logger.setLevel(loglevel)
        # noinspection PyTypeChecker
        TCPServer.__init__(self, (host, port), FloraWebSocketHandler)
        self.host = host
        self.port = self.socket.getsockname()[1]
        self.key = key
        self.cert = cert
        self.clients = []
        self.id_counter = 0
        self.thread = None
        self._deny_clients = False


class FloraFlaskWSHandler(WebSocketHandler):
    def __init__(self, socket, addr, server):
        self.app = server.app
        self.server = server
        assert not hasattr(self, "_send_lock"), "_send_lock already exists"
        self._send_lock = threading.Lock()
        if server.key and server.cert:
            try:
                socket = ssl.wrap_socket(
                    socket,
                    server_side=True,
                    certfile=server.cert,
                    keyfile=server.key
                )
            except Exception as e:
                logger.warning(
                    "SSL not available (are the paths %s and %s correct for the key and cert?)",
                    server.key, server.cert
                )
        StreamRequestHandler.__init__(self, socket, addr, server)

    def read_http_headers(self):
        self.http_get = self.rfile.readline().decode().strip()  # 保存请求行
        headers = {}
        while True:
            header_line = self.rfile.readline()
            if header_line in (b"\r\n", b"\n"):
                break
            header = header_line.decode().strip()
            if ":" not in header:
                continue
            key, value = header.split(":", 1)
            headers[key.lower().strip()] = value.strip()
        return headers

    def handshake(self):
        self.headers = self.read_http_headers()

        if self.headers.get("upgrade", "").lower() != "websocket":
            self.handle_http_request()
            return

        key = self.headers.get("sec-websocket-key")
        if not key:
            logger.error("WebSocket handshake failed: Sec-WebSocket-Key is missing")
            self.send_http_response(400, "Bad Request: Missing Sec-WebSocket-Key")
            self.keep_alive = False
            return

        try:
            response = self.make_handshake_response(key)
            with self._send_lock:
                self.request.sendall(response.encode())
            self.handshake_done = True
            self.valid_client = True
            self.server._new_client_(self)
            logger.info("WebSocket handshake successful")
        except Exception as e:
            logger.error(f"Handshake response failed to send: {e}")
            self.keep_alive = False

    def handle_http_request(self):
        headers = self.headers
        parts = self.http_get.split()
        if len(parts) < 3:
            self.send_http_response(400, "Bad Request")
            return
        method, path, version = parts
        environ = self.build_wsgi_environment(method, path, version, headers)
        content_length = int(headers.get("content-length", 0))
        environ.update({"wsgi.input": BytesIO(self.rfile.read(content_length))})
        response_iter = self.app(environ, self.start_response)
        try:
            for data in response_iter:
                self.request.sendall(data)
        finally:
            if hasattr(response_iter, "close"):
                response_iter.close()
        self.keep_alive = False

    def build_wsgi_environment(self, method, path, version, headers):
        path_parts = path.split("?", 1)
        path_info = path_parts[0]
        query_string = path_parts[1] if len(path_parts) > 1 else ""
        scheme = "https" if (self.server.key and self.server.cert) else "http"
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query_string,
            "SERVER_PROTOCOL": version,
            "wsgi.url_scheme": scheme,
            "wsgi.input": self.rfile,
            "wsgi.errors": sys.stderr,
            "wsgi.version": (1, 0),
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "SERVER_NAME": self.server.host,
            "SERVER_PORT": str(self.server.port),
        }
        for key, value in headers.items():
            wsgi_key = "HTTP_" + key.upper().replace("-", "_")
            environ.update({wsgi_key: value})
        environ.update({
            "CONTENT_TYPE": headers.get("content-type", ""),
            "CONTENT_LENGTH": headers.get("content-length", "0")
        })
        return environ

    def start_response(self, status, response_headers):
        status_line = f"HTTP/1.1 {status}\r\n"
        headers = "\r\n".join([f"{k}: {v}" for k, v in response_headers])
        self.request.sendall(f"{status_line}{headers}\r\n\r\n".encode())

    def send_http_response(self, code, message):
        response = f"HTTP/1.1 {code} {message}\r\n\r\n"
        self.request.sendall(response.encode())
        self.keep_alive = False


class FloraFlaskWSServer(WebsocketServer):
    def __init__(self, flask_app: Flask, host="127.0.0.1", port=3000, loglevel=logging.WARNING, key=None, cert=None):
        logger.setLevel(loglevel)

        class FloraFWSHandler(FloraFlaskWSHandler):
            def __init__(self, socket, addr, server):
                self.app = flask_app
                self.server = server
                assert not hasattr(self, "_send_lock"), "_send_lock already exists"
                self._send_lock = threading.Lock()
                if server.key and server.cert:
                    try:
                        socket = ssl.wrap_socket(
                            socket,
                            server_side=True,
                            certfile=server.cert,
                            keyfile=server.key
                        )
                    except Exception as e:
                        logger.warning(
                            "SSL not available (are the paths %s and %s correct for the key and cert?)",
                            server.key, server.cert
                        )
                StreamRequestHandler.__init__(self, socket, addr, server)

        # noinspection PyTypeChecker
        TCPServer.__init__(self, (host, port), FloraFWSHandler)
        self.host = host
        self.port = self.socket.getsockname()[1]
        self.key = key
        self.cert = cert
        self.clients = []
        self.id_counter = 0
        self.thread = None
        self._deny_clients = False
