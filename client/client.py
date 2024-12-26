import socket
import os
import json
import re

BUFFER_SIZE = 1400
COMMANDS = {
    "compress": {},
    "change_resolution": {"inputs": ["width", "height"]},
    "change_aspect_ratio": {"inputs": ["aspect_ratio"]},
    "extract_audio": {},
    "create_clip": {"inputs": ["start_time", "duration", "format"]},
    "cancel": {}
}


def main():
    server_address = "localhost"
    port = 9999
    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection.connect((server_address, port))

        while True:
            file_path = input("Type in the file to process: ")
            if not is_valid(file_path):
                continue

            file_name_with_extension = os.path.basename(file_path)
            file_name, media_type = os.path.splitext(file_name_with_extension)
            file_size = os.path.getsize(file_path)

            print_menu()
            command = input("Enter the command: ")
            if command not in COMMANDS:
                print("\n>> Invalid command <<\n")
                continue

            if command == "cancel":
                print("Bye!")
                break

            request = create_request(command, media_type, file_size, file_name)
            if not request:
                continue

            send_request(connection, request, file_path, file_size)
            receive_response(connection, command)

            if input("\nDo you want to continue? (y/n): ").lower() != "y":
                print("Bye!")
                break

    except ConnectionError:
        print("Connection Failed")

def is_valid(file_path):
    if not os.path.exists(file_path):
        print("File does not exist.")
        return False
    elif (file_size := os.path.getsize(file_path)) >= 4 * 1024**4:
        print("File must be below 4GB")
        return False
    return True

def print_menu():
    print("\nAvailable commands:")
    for command in COMMANDS:
        print(f"- {command}: {get_command_description(command)}")

def get_command_description(command):
    descriptions = {
        "compress": "Compress the video file.",
        "change_resolution": "Change the resolution of the video. Requires 'width' and 'height' inputs.",
        "change_aspect_ratio": "Change the aspect ratio of the video. Requires 'aspect_ratio' input.",
        "extract_audio": "Extract the audio track from the video.",
        "create_clip": "Create a clip from the video. Requires 'start_time', 'duration', and 'format' inputs.",
        "cancel": "Exit the program."
    }
    return descriptions.get(command, "No description available.")

def create_request(command, media_type, file_size, file_name):
    inputs = COMMANDS[command].get("inputs", [])
    request_data = {"command": command}

    for input_name in inputs:
        print(input_name)
        prompt_message = get_input_prompt(input_name)
        value = input(prompt_message)
        if not validate_input(input_name, value):
            print(f"Invalid {input_name}. Retry.")
            return None
        request_data[input_name] = value

    return {
        "request": request_data,
        "media type": media_type,
        "file size": file_size,
        "file name": file_name
    }

def get_input_prompt(input_name):
    prompts = {
        "width": "Enter the width (e.g., 1920): ",
        "height": "Enter the height (e.g., 1080): ",
        "aspect_ratio": "Enter the aspect ratio (e.g., 16:9): ",
        "start_time": "Enter the start time (e.g., 00:01:30 h:m:s(.ms)or 90(seconds)): ",
        "duration": "Enter the duration in seconds (e.g., 00:01:05 h:m:s(.ms) or 10(seconds))): ",
        "format": "Enter the format (gif or webm): "
    }
    return prompts.get(input_name, f"Enter {input_name}: ")


def validate_input(input_name, value):
    if input_name in ["width", "height"]:
        return value.isdigit()
    elif input_name == "aspect_ratio":
        return re.match(r"^\d+:\d+$", value)
    elif input_name in ["start_time", "duration"]:
        return value.replace('.', '', 1).isdigit() or re.match(r"^\d{1,2}:\d{2}:\d{2}(\.\d{1,3})?$", value)
    elif input_name == "format":
        return value.lower() in ["gif", "webm"]
    return True

def send_request(connection, request, file_path, file_size):
    request_json = json.dumps(request).encode()
    request_size = len(request_json)
    connection.sendall(request_size.to_bytes(2, "big") + request_json)

    with open(file_path, "rb") as f:
        total_data = 0
        while (data := f.read(BUFFER_SIZE)):
            total_data += len(data)
            print(f"Uploading... {total_data} / {file_size}")
            connection.sendall(data)
        print("Uploaded")

def receive_response(connection, command):
    response_size = int.from_bytes(connection.recv(5), "big")
    response = json.loads(connection.recv(response_size).decode())

    if response["status"] == "error":
        print(response["message"])
        return

    file_name = response["file name"]
    file_size = response["file size"]

    output_dir = os.path.join("processed", command)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, file_name)

    file_data = b''
    while len(file_data) < file_size:
        file_data += connection.recv(BUFFER_SIZE)
        print(f"Downloading... {len(file_data)} / {file_size}")

    with open(output_file, "wb") as f:
        f.write(file_data)
    print("\nCompleted. Check the processed folder.")

if __name__ == "__main__":
    main()
