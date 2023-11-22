#!/bin/bash

# Check if the certificate and key files already exist
CERT_FILE="certificate.pem"
KEY_FILE="key.pem"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Generating SSL certificate..."
    openssl req -newkey rsa:2048 -nodes -keyout $KEY_FILE -x509 -days 365 -out $CERT_FILE -subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=www.example.com"
else
    echo "SSL certificate already exists. Skipping generation..."
fi

# Get the local IP address of the computer
# Using 'ifconfig' and 'awk' to find the first non-127.0.0.1 address
LOCAL_IP=$(ipconfig getifaddr en0)


# Python script to run an HTTPS server
cat <<EOF > https_server.py
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
context.load_cert_chain(certfile='$CERT_FILE', keyfile='$KEY_FILE')
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving at https://{LOCAL_IP}:4443")
httpd.serve_forever()
EOF

# Set the environment variable for local IP
export LOCAL_IP=$LOCAL_IP

# Run the Python HTTPS server
python3 https_server.py
