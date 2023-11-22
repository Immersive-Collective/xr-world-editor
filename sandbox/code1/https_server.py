import http.server, ssl, webbrowser, os

# Fetching local IP from environment variable
LOCAL_IP = os.getenv('LOCAL_IP')

class Server(http.server.HTTPServer):
    def server_activate(self):
        webbrowser.open(f'https://{LOCAL_IP}:4443')  # Open the default browser
        http.server.HTTPServer.server_activate(self)

server_address = ('', 4443)  # Empty string for hostname means bind to all interfaces
httpd = Server(server_address, http.server.SimpleHTTPRequestHandler)

# Using SSLContext instead of deprecated ssl.wrap_socket()
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile='certificate.pem', keyfile='key.pem')
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving at https://{LOCAL_IP}:4443")
httpd.serve_forever()
