const fs = require('fs');
const https = require('https');
const WebSocket = require('ws');

// Load SSL certificate and key
const cert = fs.readFileSync('../code1/certificate.pem');
const key = fs.readFileSync('../code1/key.pem');

// Create an HTTPS server with your SSL certificate and key
const server = https.createServer({
    cert: cert,
    key: key
});

// Create a WebSocket server on top of the HTTPS server
const wss = new WebSocket.Server({ server });

wss.on('connection', ws => {
    // Handle WebSocket connections
    // ...
    console.log('connection')
});

// Start the server on a port (e.g., 8080)
server.listen(8080, () => {
    console.log('Secure WebSocket server started on port 8080');
});
