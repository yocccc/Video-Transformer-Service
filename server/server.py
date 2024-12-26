import socket
import ffmpeg
import json
import os
import datetime
import threading

BUFFER_SIZE = 1400
TEMP_DIR = "temp"
PROCESSED_DIR = "processed"
PORT = 9999
SERVER_ADDRESS = "0.0.0.0"

class File:
    def __init__(self, file_name, media_type):
        self.file_name = file_name
        self.media_type = media_type
        self.datetime = datetime.datetime.now().strftime("%Y%m%d %H%M%S")

    def get_file_name(self,is_original=False):
        if is_original:
            return f"{self.file_name}{self.media_type}"
        else:
            return f"{self.datetime} {self.file_name}{self.media_type}"

    def set_media_type(self, media_type):
        self.media_type = media_type

def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((SERVER_ADDRESS, PORT))
    sock.listen()
    print("Server is listening for connections...")

    while True:
        connection, address = sock.accept()
        threading.Thread(target=handle_client, args=(connection, address), daemon=True).start()

def handle_client(connection, address):
    print(f"Connected to {address}")
    while True:
        try:
            print("Waiting for header...")
            header_size = connection.recv(2)
            if not header_size:
                print("Connection closed by the client.")
                break

            header_size = int.from_bytes(header_size, "big")
            header = connection.recv(header_size)
            header = json.loads(header.decode())

            file_size = header["file size"]
            media_type = header["media type"]
            file_name = header["file name"]
            req = header["request"]

            file_data = receive_file_data(connection, file_size)
            file = save_temp_file(file_name, media_type, file_data)

            process_request(req, file)
            send_processed_file(connection, file)

        except ffmpeg._run.Error:
            send_error_response(connection, "This command or argument ar is not valid")
        except Exception as e:
            print(f"Error: {e}")
            #send_error_response(connection, str(e))

def receive_file_data(connection, file_size):
    file_data = b""
    while len(file_data) < file_size:
        data = connection.recv(BUFFER_SIZE)
        file_data += data
        #print(f"Current total data size = {len(file_data)}/{file_size}")
    return file_data

def save_temp_file(file_name, media_type, file_data):
    file = File(file_name, media_type)
    temp_path = os.path.join(TEMP_DIR, file.get_file_name())
    with open(temp_path, "wb") as f:
        f.write(file_data)
    return file

def process_request(req, file):
    print("Processing request...")
    command = req["command"]
    file_name = file.get_file_name()
    input_file = os.path.join(TEMP_DIR, file_name)
    output_file = os.path.join(PROCESSED_DIR, file_name)

    if command == "compress":
        compress_video(input_file, output_file, "1M")
    elif command == "change_resolution":
        change_resolution(input_file, output_file, req["width"], req["height"])
    elif command == "change_aspect_ratio":
        change_aspect_ratio(input_file, output_file, req["aspect_ratio"])
    elif command == "extract_audio":
        file.set_media_type(".mp3")
        output_file = os.path.join(PROCESSED_DIR, file.get_file_name())
        extract_audio(input_file, output_file)
    elif command == "create_clip":
        file.set_media_type(f".{req['format']}")
        output_file = os.path.join(PROCESSED_DIR, file.get_file_name())
        create_clip(input_file, output_file, req["start_time"], req["duration"], req["format"])
    else:
        raise ValueError(f"Unknown command: {command}")

    print("Processing complete.")

def compress_video(input_file, output_file, bitrate="1M"):
    ffmpeg.input(input_file).output(output_file, video_bitrate=bitrate).run()

def change_resolution(input_file, output_file, width, height):
    ffmpeg.input(input_file).output(output_file, vf=f'scale={width}:{height}').run()

def change_aspect_ratio(input_file, output_file, aspect_ratio):
    ffmpeg.input(input_file).output(output_file, vf=f'setdar={aspect_ratio}').run()

def extract_audio(input_file, output_file):
    ffmpeg.input(input_file).output(output_file, acodec="mp3", vn=None).run()

def create_clip(input_file, output_file, start_time, duration, format):
    ffmpeg.input(input_file, ss=start_time, t=duration).output(output_file, format=format, vf="fps=10").run()

def send_processed_file(connection, file):
    file_path = os.path.join(PROCESSED_DIR, file.get_file_name())
    with open(file_path, "rb") as f:
        file_size = os.path.getsize(file_path)
        res = {
            "status": "success",
            "file name": file.get_file_name(is_original=True),
            "file size": file_size,
        }
        send_response(connection, res)

        print("Sending file data...")
        while (data := f.read(BUFFER_SIZE)):
            #print(f"sending... {total_data}/{file_size}")
            connection.sendall(data)
        print("File data sent.")

def send_error_response(connection, message):
    res = {
        "status": "error",
        "message": message
    }
    send_response(connection, res)

def send_response(connection, res):
    res = json.dumps(res).encode()
    res_size = len(res)
    connection.sendall(res_size.to_bytes(5, "big"))
    connection.sendall(res)

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))
    main()
