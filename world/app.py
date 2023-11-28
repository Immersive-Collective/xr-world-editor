from flask import Flask, request, jsonify, send_from_directory, render_template, url_for
import asyncio
import threading
import json
import os
import uuid
import time
import base64
import ssl
import websockets
import atexit
from datetime import datetime

app = Flask(__name__)


import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

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


@atexit.register
def on_app_shutdown():
    set_restart_flag()


def check_restart():
    flag_file = "restart.flag"
    restarted = os.path.exists(flag_file)
    if restarted:
        os.remove(flag_file)
    return restarted


def set_restart_flag():
    with open("restart.flag", "w") as f:
        f.write("restarting")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["POST"])
async def upload_file():
    file = request.files.get("file")
    uploader_id = request.form.get("uploader")  # Retrieve uploader ID from form data
    position = request.form.get("position")
    scale = request.form.get("scale")
    quaternion = request.form.get("quaternion")

    if file and allowed_file(file.filename):
        unique_id = str(uuid.uuid4())
        timestamp = str(int(time.time()))
        filename = unique_id + "_" + timestamp + os.path.splitext(file.filename)[1]
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        upload_time = datetime.now().isoformat()

        metadata = {
            "uuid": unique_id,
            "original_name": file.filename,
            "position": position,
            "scale": scale,
            "quaternion": quaternion,
            "uploader": uploader_id,
            "timestamp": timestamp,
            "upload_time": upload_time,
            "client_ip": request.remote_addr,
            "file_size": os.path.getsize(file_path),
        }
        with open(os.path.join(UPLOAD_FOLDER, unique_id + ".json"), "w") as json_file:
            json.dump(metadata, json_file)

        # model_data = {
        #     "uuid": unique_id,
        #     "original_name": file.filename,
        #     "position": position,
        #     "scale": scale,
        #     "quaternion": quaternion,
        #     "uploader": uploader_id,
        #     "timestamp": timestamp,
        #     "upload_time": upload_time,
        #     "client_ip": request.remote_addr,
        #     "file_size": os.path.getsize(file_path),
        # }

        models[unique_id] = metadata

        # Broadcast the new model to all clients except the uploader
        # broadcast_new_model(unique_id, model_data, uploader_id)
        # sendall(
        #     json.dumps(
        #         {
        #             "type": "newModel",
        #             "client_id": unique_id,
        #             "position": position,
        #         }
        #     )
        # )

        return jsonify({"uuid": unique_id})
    else:
        return jsonify({"error": "File type not allowed"}), 400


# async def broadcast_new_model(uuid, model_data, uploader_id):
#     print("broadcast_new_model", uuid)
#     message = json.dumps({"type": "newModel", "uuid": uuid, "model": model_data})
#     for client_id, client_info in clients.items():
#         if client_info["uuid"] != uploader_id:
#             await client_info["websocket"].send(message)


@app.route("/world/models/<filename>")
def serve_model(filename):
    return send_from_directory(WORLD_MODELS_DIR, filename)


@app.route("/")
def index():
    return render_template("index.html")


# WebSocket server setup
clients = {}
models = {}


def sync_broadcast(message):
    for client_id, client_info in clients.items():
        send_message_sync(client_info["websocket"], message)


async def sendall(message):
    for client_id in clients:
        client = clients[client_id]["websocket"]
        await client.send(message)


async def sendall_except_sender(message, sender_uuid):
    for client_id in clients:
        if client_id != sender_uuid:
            client = clients[client_id]["websocket"]
            await client.send(message)


async def websocket_handler(websocket, path):
    client_uuid = str(uuid.uuid4())  # Changed variable name to client_uuid
    clients[client_uuid] = {"websocket": websocket}

    await websocket.send(
        json.dumps({"type": "existingModels", "models": list(models.values())})
    )

    if check_restart():
        # await websocket.send(json.dumps({"command": "reload"}));
        await sendall(
            json.dumps(
                {
                    "command": "reload",
                }
            )
        )

    print("New client connected:", client_uuid)

    # Notify all clients about the new connection
    connected_client_ids = list(clients.keys())
    await sendall(
        json.dumps(
            {
                "type": "clientConnected",
                "client_id": client_uuid,
                "clients": connected_client_ids,
            }
        )
    )

    try:
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data["type"] == "register":
                print(" + register:")
                # Handle 'register' message type...
                clients[client_uuid]["get_file_path_from_uuid"] = data["uuid"]
                await sendall(
                    json.dumps(
                        {
                            "type": "broadcast",
                            "content": "New client registered: " + data["uuid"],
                            "clients": connected_client_ids,
                        }
                    )
                )

            elif data["type"] == "requestModel":
                print(" + requestModel:")
                model_uuid = data["uuid"]
                position = data["position"]
                file_path = get_file_path_from_uuid(model_uuid)
                if file_path:
                    with open(file_path, "rb") as file:
                        contents = file.read()
                        # Check if the file size is greater than zero
                        if len(contents) > 0:
                            try:
                                encoded_contents = base64.b64encode(contents).decode(
                                    "utf-8"
                                )
                                # Further check if the encoded content is not empty
                                if encoded_contents:
                                    response = {
                                        "type": "modelData",
                                        "data": encoded_contents,
                                        "position": position,
                                        "url_uuid": model_uuid,
                                    }
                                    await websocket.send(
                                        json.dumps(response)
                                    )  # Send only to requesting client
                                else:
                                    print(
                                        f"Error encoding file contents for UUID: {model_uuid}"
                                    )
                            except Exception as e:
                                print(
                                    f"Error encoding file for UUID: {model_uuid}: {e}"
                                )
                        else:
                            print(f"File is empty for UUID: {model_uuid}")
                else:
                    print(f"File not found for UUID: {model_uuid}")

            elif data["type"] == "requestNewModel":
                print(" + requestNewModel:")
                model_uuid = data["uuid"]
                position = data["position"]
                file_path = get_file_path_from_uuid(model_uuid)
                if file_path:
                    with open(file_path, "rb") as file:
                        contents = file.read()
                        file_size = len(contents)
                        print(f"File size for UUID {model_uuid}: {file_size} bytes")
                        # await asyncio.sleep(2)  # 2 seconds delay after reading the file

                        if len(contents) > 0:
                            try:
                                encoded_contents = base64.b64encode(contents).decode(
                                    "utf-8"
                                )
                                # await asyncio.sleep(2)  # 2 seconds delay after encoding the contents
                                if encoded_contents:
                                    response = {
                                        "type": "newModelData",
                                        "data": encoded_contents,
                                        "position": position,
                                        "url_uuid": model_uuid,
                                    }
                                    await websocket.send(
                                        json.dumps(response)
                                    )  # Send to requesting client
                                else:
                                    print(
                                        f"Error encoding file contents for UUID: {model_uuid}"
                                    )
                            except Exception as e:
                                print(
                                    f"Error encoding file for UUID: {model_uuid}: {e}"
                                )
                        else:
                            print(f"File is empty for UUID: {model_uuid}")
                else:
                    print(f"File not found for UUID: {model_uuid}")

            elif data["type"] == "broadcastNewModel":
                message = json.dumps(
                    {"type": "existingModels", "models": list(models.values())}
                )
                for client_id, client_info in clients.items():
                    if client_info["websocket"] != websocket:
                        await client_info["websocket"].send(message)

            elif data["type"] == "removeModel":
                model_uuid = data["uuid"]
                print(f" - removeModel: {model_uuid}")
                if model_uuid in models:
                    del models[model_uuid]
                # Broadcast removal to all clients
                await sendall(json.dumps({"type": "modelRemoved", "uuid": model_uuid}))

            elif data["type"] == "broadcastObjectChange":
                print(" - broadcastObjectChange:")

                model_uuid = data["uuid"]
                props = data["value"]
                propName = data["propName"]
                clientID = data["clientID"]

                if model_uuid in models:
                    if propName == "position":
                        models[model_uuid]["position"] = [
                            props["x"],
                            props["y"],
                            props["z"],
                        ]
                    elif propName == "scale":
                        models[model_uuid]["scale"] = [
                            props["x"],
                            props["y"],
                            props["z"],
                        ]
                    elif propName == "quaternion":
                        models[model_uuid]["quaternion"] = [
                            props["x"],
                            props["y"],
                            props["z"],
                            props["w"],
                        ]

                    data = {
                        "type": "modelUpdated",
                        "uuid": model_uuid,
                        "propName": propName,
                        "model": models[model_uuid],
                    }

                    # models[model_uuid] =

                    await sendall_except_sender(json.dumps(data), clientID)
                else:
                    print(f"Model with UUID {model_uuid} not found")

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected:", client_uuid)
        del clients[client_uuid]
        # Notify all clients about the disconnection
        connected_client_ids = list(clients.keys())
        await sendall(
            json.dumps(
                {
                    "type": "clientDisconnected",
                    "client_id": client_uuid,
                    "clients": connected_client_ids,
                }
            )
        )


def get_file_path_from_uuid(uuid):
    try:
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith(uuid) and not filename.endswith(".json"):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    logging.info(f"File found for UUID {uuid}: {file_path}")
                    return file_path
                else:
                    logging.warning(f"File does not exist for UUID {uuid}: {file_path}")
        logging.warning(f"No file found for UUID {uuid}")
        return None
    except Exception as e:
        logging.error(f"Error in get_file_path_from_uuid for UUID {uuid}: {e}")
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
#
#
#
