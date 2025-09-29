import os

EXCLUDED_DIRS = {'Scripts', 'venv', 'env', 'staticfiles'}

def list_directory_structure(root_dir, indent=0):
    for item in sorted(os.listdir(root_dir)):
        item_path = os.path.join(root_dir, item)

        # Skip excluded directories
        if item in EXCLUDED_DIRS:
            continue

        # Print directories
        if os.path.isdir(item_path):
            print('│   ' * indent + f'├── {item}/')
            list_directory_structure(item_path, indent + 1)
        else:
            print('│   ' * indent + f'├── {item}')

if __name__ == '__main__':
    current_dir = os.getcwd()
    print(f"📂 Directory Structure of: {current_dir}\n")
    list_directory_structure(current_dir)
