# xr-world-editor
Editor for XR Worlds





# running code from sandbox/codeNN

```
start.sh
```

This script sets up a simple HTTPS server on your local machine using Python. It automatically generates a self-signed SSL certificate if one doesn't already exist and starts a web server accessible via the local IP address. This is useful for testing web applications locally with HTTPS.

## How to Run

### Prerequisites
- Ensure you have Python 3 installed on your system.
- OpenSSL should be available on your system for generating SSL certificates.

### Steps to Run
1. **Run the Script**: Execute the provided Bash script. It will check for existing SSL certificates and create them if necessary. Then it starts a Python HTTPS server.
   
   ```bash
   ./<script-name>.sh
   ```
   Replace `<script-name>` with the name of the script file.

2. **Access the Server**: Once the server is running, it will open your default web browser and navigate to the HTTPS server hosted at `https://<your-local-ip>:4443`. You can also manually navigate to this URL in any web browser.

### Important Notes
- The SSL certificate generated is self-signed and may cause security warnings in your browser. This is expected behavior for local testing.
- The script automatically detects and uses your machine's local IP address. Ensure that your firewall settings allow inbound connections to port 4443.


