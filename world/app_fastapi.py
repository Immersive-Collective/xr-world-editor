from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    WebSocket,
    Request,
)  # Added Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Mount
from jinja2 import Environment, FileSystemLoader

import asyncio
import json
import os
import uuid
import time
import base64
from datetime import datetime

app = FastAPI()

# Directory setup
# Directory and Template setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
WORLD_MODELS_DIR = os.path.join(BASE_DIR, "world", "models")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Static files setup
app.mount(
    "/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static"
)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "bmp", "hdr", "glb", "gltf"}
clients = {}
models = {}


@app.on_event("shutdown")
def on_app_shutdown():
    set_restart_flag()


def set_restart_flag():
    with open("restart.flag", "w") as f:
        f.write("restarting")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), uploader: str = Form(...), position: str = Form(...)
):
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="File type not allowed")

    unique_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))
    filename = f"{unique_id}_{timestamp}{os.path.splitext(file.filename)[1]}"
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())  # Writing the file

    upload_time = datetime.now().isoformat()
    metadata = {
        "original_name": file.filename,
        "position": position,
        "uploader": uploader,
        "timestamp": timestamp,
        "upload_time": upload_time,
        "client_ip": "request.client.host",  # request.client.host placeholder
        "file_size": os.path.getsize(file_path),
    }

    with open(os.path.join(UPLOAD_FOLDER, f"{unique_id}.json"), "w") as json_file:
        json.dump(metadata, json_file)

    model_data = {
        "uuid": unique_id,
        "position": position,
        "filename": filename,
    }
    models[unique_id] = model_data

    await broadcast_new_model(unique_id, model_data, uploader)

    return {"uuid": unique_id}


@app.get("/world/models/{filename}")
async def serve_model(filename: str):
    return FileResponse(os.path.join(WORLD_MODELS_DIR, filename))


# Templates configuration
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def broadcast_new_model(uuid, model_data, uploader_id):
    message = json.dumps({"type": "newModel", "uuid": uuid, "model": model_data})
    for client_id, client_info in clients.items():
        if client_info["uuid"] != uploader_id:
            await client_info["websocket"].send_text(message)


@app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    client_uuid = str(uuid.uuid4())
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
                clients[client_uuid]["uuid"] = data["uuid"]
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
                            "url_uuid": model_uuid,
                        }
                        await websocket.send(
                            json.dumps(response)
                        )  # Send only to requesting client
                else:
                    print(f"File not found for UUID: {model_uuid}")

            elif data["type"] == "removeModel":
                print(" - removeModel:")
                model_uuid = data["uuid"]
                if model_uuid in models:
                    del models[model_uuid]
                # Broadcast removal to all clients
                await sendall(json.dumps({"type": "modelRemoved", "uuid": model_uuid}))

            elif data["type"] == "updateModelPosition":
                print(" - updateModelPosition:")
                model_uuid = data["uuid"]
                new_position = data[
                    "position"
                ]  # Assuming this is a dictionary with x, y, z
                if model_uuid in models:
                    models[model_uuid]["position"] = new_position
                    # Broadcast updated position to all clients
                    await sendall(
                        json.dumps(
                            {
                                "type": "modelPositionUpdated",
                                "uuid": model_uuid,
                                "position": new_position,
                            }
                        )
                    )

            # Additional message types can be added here...

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
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(uuid):
            return os.path.join(UPLOAD_FOLDER, filename)
    return None


async def start_websocket_server():
    async with websockets.serve(websocket_handler, "0.0.0.0", 5000, ssl=context):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app, host="0.0.0.0", port=5001, ssl_keyfile="key.pem", ssl_certfile="cert.pem"
    )
