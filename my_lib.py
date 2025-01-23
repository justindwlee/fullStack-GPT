def save_file(file, folder_path):
    file_content = file.read()
    file_path = f"{folder_path}/{file.name}"
    with open(file_path, "wb") as f:
        f.write(file_content)