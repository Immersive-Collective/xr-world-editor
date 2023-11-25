from flask import Flask, request, jsonify, send_from_directory, render_template
import asyncio
import threading
import json
import os
import uuid
import time
import base64
import ssl
import websockets

app = Flask(__name__)

# SSL context for secure connections
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("cert.pem", "key.pem")

# Directory setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
WORLD_MODELS_DIR = os.path.join(BASE_DIR, "world", "models")

# Create directories if they don't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(WORLD_MODELS_DIR):
    os.makedirs(WORLD_MODELS_DIR)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "bmp", "hdr", "glb", "gltf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if file and allowed_file(file.filename):
        unique_id = str(uuid.uuid4())
        timestamp = str(int(time.time()))
        filename = unique_id + "_" + timestamp + os.path.splitext(file.filename)[1]
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        metadata = {
            "original_name": file.filename,
            "client_ip": request.remote_addr,
            "file_size": os.path.getsize(file_path),
        }
        with open(os.path.join(UPLOAD_FOLDER, unique_id + ".json"), "w") as json_file:
            json.dump(metadata, json_file)
        return jsonify({"uuid": unique_id})
    else:
        return jsonify({"error": "File type not allowed"}), 400


@app.route("/world/models/<filename>")
def serve_model(filename):
    return send_from_directory(WORLD_MODELS_DIR, filename)


@app.route("/")
def index():
    return render_template("index.html")


# WebSocket server setup
clients = {}


async def sendall(message):
    for client_id in clients:
        client = clients[client_id]["websocket"]
        await client.send(message)


async def websocket_handler(websocket, path):
    client_uuid = str(uuid.uuid4())  # Changed variable name to client_uuid
    clients[client_uuid] = {"websocket": websocket}
    print("New client connected:", client_uuid)

    # Notify all clients about the new connection
    await sendall(json.dumps({"type": "clientConnected", "client_id": client_uuid}))

    try:
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data["type"] == "register":
                # Handle 'register' message type...
                clients[client_uuid]["uuid"] = data["uuid"]
                await sendall(
                    json.dumps(
                        {
                            "type": "broadcast",
                            "content": "New client registered: " + data["uuid"],
                        }
                    )
                )

            elif data["type"] == "requestModel":
                model_uuid = data["uuid"]  # Changed variable name to model_uuid
                pos = data["pos"]
                file_path = get_file_path_from_uuid(model_uuid)
                if file_path:
                    with open(file_path, "rb") as file:
                        contents = file.read()
                        encoded_contents = base64.b64encode(contents).decode("utf-8")
                        response = {
                            "type": "modelData",
                            "data": encoded_contents,
                            "pos": pos,
                        }
                        await sendall(json.dumps(response))
                else:
                    print(f"File not found for UUID: {model_uuid}")

            # Additional message types can be added here...
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected:", client_uuid)
        del clients[client_uuid]
        # Notify all clients about the disconnection
        await sendall(
            json.dumps({"type": "clientDisconnected", "client_id": client_uuid})
        )


def get_file_path_from_uuid(uuid):
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(uuid):
            return os.path.join(UPLOAD_FOLDER, filename)
    return None


async def start_websocket_server():
    async with websockets.serve(websocket_handler, "0.0.0.0", 5000, ssl=context):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    # Starting WebSocket server in a separate thread
    ws_thread = threading.Thread(target=lambda: asyncio.run(start_websocket_server()))
    ws_thread.daemon = True
    ws_thread.start()

    # Run Flask app
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
        use_reloader=False,
        ssl_context=("cert.pem", "key.pem"),
    )


# For Unix/Linux/macOS
# export FLASK_ENV=development
# flask run --host=0.0.0.0 --port=5001
