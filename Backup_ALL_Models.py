import subprocess
import re
import os
import shutil
import platform

#****************************************************************
#****************************************************************
#****************************************************************
# Your ollama model folder:
Ollama_Model_Folder = os.path.expanduser("~/.ollama/models")

# Where you want to back up your models:
BackUp_Folder = "/Volumes/LLM backup"
#****************************************************************
#****************************************************************
#****************************************************************

def sanitize_filename_MF(name):
    name = name.replace(":latest","")
    return re.sub(r'[<>:"/\\|?*.]', '-', name)

def run_command(command):
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )

    output_text, error_text = process.communicate()
    
    if error_text and error_text.strip():
        print(f"Warning: Command '{command}' produced error: {error_text}")
        
    return output_text.strip()

def create_ollama_model_file(model_name, output_file, BackUp_Folder, Ollama_Model_Folder):
    # First, get the modelfile to extract the blob path
    modelfile_command = f'ollama show --modelfile {model_name}'
    modelfile_message = run_command(modelfile_command)
    
    if not modelfile_message:
        print(f"Error: Could not retrieve modelfile for '{model_name}'")
        return False
    
    # Extract model file path using regex - looking for FROM line that contains path to blob
    model_file_path = None
    from_match = re.search(r'FROM\s+(\/.*?\/\.ollama\/models\/blobs\/[^\s\n]+)', modelfile_message)
    
    if not from_match:
        print(f"Error: Could not find model file path in modelfile for '{model_name}'")
        print("Modelfile content:")
        print(modelfile_message[:500] + "..." if len(modelfile_message) > 500 else modelfile_message)
        return False
    
    model_file_path = from_match.group(1)
    
    if not os.path.exists(model_file_path):
        print(f"Error: Model file not found at path: {model_file_path}")
        return False
    
    # Get template, parameters, and system prompt
    template_command = f'ollama show --template {model_name}'
    template = run_command(template_command)
    
    parameters_command = f'ollama show --parameters {model_name}'
    parameters = run_command(parameters_command)
    
    system_command = f'ollama show --system {model_name}'
    system_message = run_command(system_command)
    
    # Prepare backup folder
    sanitized_model_name = sanitize_filename_MF(model_name)
    new_folder_path = os.path.join(BackUp_Folder, sanitized_model_name)
    
    if os.path.exists(new_folder_path) and os.path.isdir(new_folder_path):
        print(f"Model: '{model_name}' already exists in the backup folder, so it will be skipped.")
        return True
    
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
        print(f"Created folder: {new_folder_path}")
    
    # Create the ModelFile
    model_content = f"""FROM {sanitized_model_name}.gguf
TEMPLATE """ + '"""' + f"""{template}""" + '"""' + "\n"
    
    for line in parameters.splitlines():
        model_content += f'PARAMETER {line}\n'
    
    if system_message:
        model_content += f'SYSTEM "{system_message}"\n'
    
    with open(os.path.join(new_folder_path, output_file), 'w') as file:
        file.write(model_content)
    
    print(f'Model file created: {os.path.join(new_folder_path, output_file)}')
    
    # Copy the model file
    new_model_file_name = f"{sanitized_model_name}.gguf"
    new_model_file_path = os.path.join(new_folder_path, new_model_file_name)

    print(f"Copying model file from {model_file_path} (this may take a while for large models)...")
    
    try:
        shutil.copy2(model_file_path, new_model_file_path)
        print(f"Successfully copied model file to: {new_model_file_path}")
        return True
    except Exception as e:
        print(f"Error copying model file: {str(e)}")
        return False

def process_models(model_names):
    # Check if backup folder exists and is mounted
    if not os.path.exists(BackUp_Folder):
        print(f"Error: Backup folder '{BackUp_Folder}' does not exist. Please check the path and make sure the drive is mounted.")
        return
    
    # Check if we have write permissions
    if not os.access(BackUp_Folder, os.W_OK):
        print(f"Error: No write permission to backup folder '{BackUp_Folder}'.")
        return
    
    # Check if Ollama model folder exists
    if not os.path.exists(Ollama_Model_Folder):
        print(f"Error: Ollama model folder '{Ollama_Model_Folder}' does not exist. Please check the path.")
        return
    
    total_models = len(model_names)
    successful = 0
    skipped = 0
    failed = 0
    
    print(f"Starting backup of {total_models} models to {BackUp_Folder}")
    print("-" * 60)
    
    for i, model_name in enumerate(model_names, 1):
        model_name = model_name.strip()
        if not model_name:
            continue
            
        print(f"Processing model {i}/{total_models}: {model_name}")
        output_file = "ModelFile"
        
        try:
            result = create_ollama_model_file(model_name, output_file, BackUp_Folder, Ollama_Model_Folder)
            if result:
                successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Error processing model {model_name}: {str(e)}")
            failed += 1
        
        print("-" * 60)
    
    print(f"Backup completed. Summary:")
    print(f"Total models: {total_models}")
    print(f"Successfully backed up: {successful}")
    print(f"Skipped (already exist): {skipped}")
    print(f"Failed: {failed}")

def extract_names(data):
    try:
        lines = data.strip().split('\n')
        # Skip the header line and extract the first column (model name)
        names = []
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if parts:  # Make sure the line is not empty
                name = parts[0]
                names.append(name)
        return names
    except Exception as e:
        print(f"Error extracting model names: {str(e)}")
        return []

# Main execution logic wrapped in a try-except block
def main():
    try:
        print("Ollama Backup Tool")
        print(f"System: {platform.system()} {platform.release()}")
        print(f"Ollama model folder: {Ollama_Model_Folder}")
        print(f"Backup destination: {BackUp_Folder}")
        print("-" * 60)
        
        # Get list of models
        print("Getting list of models...")
        data = run_command("ollama list")
        if not data:
            print("Error: Failed to get model list. Make sure ollama is installed and running.")
            return 1
        
        model_names = extract_names(data)
        
        if not model_names:
            print("No models found to backup.")
            return 0
        
        print(f"Found {len(model_names)} models.")
        process_models(model_names)
        return 0

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

# Add this for proper Python module behavior
if __name__ == "__main__":
    main()
