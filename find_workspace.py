import os
import json
import shutil
import re
import argparse
from urllib.parse import unquote

def find_workspace_files():
    """Find all workspace folders and their corresponding state.vscdb files."""
    # Get the AppData Roaming path
    appdata = os.environ.get('APPDATA')
    if not appdata:
        print("Error: APPDATA environment variable not found.")
        return []
    
    # Construct the workspace storage path
    workspace_storage_path = os.path.join(appdata, 'Cursor', 'User', 'workspaceStorage')
    if not os.path.exists(workspace_storage_path):
        print(f"Error: Workspace storage directory not found at: {workspace_storage_path}")
        return []
    
    workspaces = []
    
    print(f"Scanning for workspaces in: {workspace_storage_path}")
    
    # Iterate through each folder in the workspace storage directory
    for folder_name in os.listdir(workspace_storage_path):
        folder_path = os.path.join(workspace_storage_path, folder_name)
        
        if not os.path.isdir(folder_path):
            continue
        
        # Look for workspace.json to identify the workspace
        workspace_json_path = os.path.join(folder_path, 'workspace.json')
        state_vscdb_path = os.path.join(folder_path, 'state.vscdb')
        
        workspace_name = None
        workspace_folder = None
        
        # Check if the workspace.json file exists
        if os.path.exists(workspace_json_path):
            try:
                with open(workspace_json_path, 'r', encoding='utf-8') as f:
                    workspace_data = json.load(f)
                    
                    # Extract the workspace folder path
                    if 'folder' in workspace_data:
                        folder_uri = workspace_data['folder']
                        
                        # Clean up the URI to get a readable path
                        if folder_uri.startswith('file:///'):
                            # Remove the 'file:///' prefix and decode URL encoding
                            decoded_path = unquote(folder_uri[8:])
                            workspace_folder = decoded_path
                            
                            # Extract the workspace name from the path
                            workspace_name = os.path.basename(decoded_path)
            except Exception as e:
                print(f"Error reading workspace.json in {folder_name}: {str(e)}")
        
        # Check if the state.vscdb file exists
        has_state_db = os.path.exists(state_vscdb_path)
        
        workspaces.append({
            'hash': folder_name,
            'name': workspace_name,
            'folder': workspace_folder,
            'state_db_path': state_vscdb_path if has_state_db else None,
            'has_state_db': has_state_db
        })
    
    return workspaces

def copy_state_db(state_db_path, output_dir='.', new_name=None):
    """Copy a state.vscdb file to the output directory."""
    if not state_db_path or not os.path.exists(state_db_path):
        print(f"Error: State DB file not found at: {state_db_path}")
        return False
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if new_name:
        output_path = os.path.join(output_dir, new_name)
    else:
        # Use the original filename
        output_path = os.path.join(output_dir, os.path.basename(state_db_path))
    
    try:
        shutil.copy2(state_db_path, output_path)
        print(f"Successfully copied state DB to: {output_path}")
        return True
    except Exception as e:
        print(f"Error copying state DB: {str(e)}")
        return False

def interactive_mode():
    """Run the tool in interactive mode."""
    workspaces = find_workspace_files()
    
    if not workspaces:
        print("No workspaces found.")
        return
    
    print(f"\nFound {len(workspaces)} workspace folders:")
    print("-" * 80)
    print(f"{'#':<3} {'Workspace Name':<30} {'Has DB':<8} {'Hash':<35}")
    print("-" * 80)
    
    for i, workspace in enumerate(workspaces):
        workspace_name = workspace['name'] or 'Unknown'
        has_db = "✓" if workspace['has_state_db'] else "✗"
        print(f"{i+1:<3} {workspace_name:<30} {has_db:<8} {workspace['hash']}")
    
    print("-" * 80)
    
    while True:
        try:
            choice = input("\nEnter the number of the workspace to copy its state.vscdb (or 'q' to quit): ")
            
            if choice.lower() == 'q':
                break
            
            idx = int(choice) - 1
            if idx < 0 or idx >= len(workspaces):
                print("Invalid selection. Please try again.")
                continue
            
            selected = workspaces[idx]
            
            if not selected['has_state_db']:
                print(f"The selected workspace ({selected['name']}) does not have a state.vscdb file.")
                continue
            
            workspace_name = selected['name'] or 'unknown'
            safe_name = re.sub(r'[^\w\s-]', '', workspace_name).strip().replace(' ', '_')
            new_filename = f"{safe_name}_state.vscdb"
            
            copy_state_db(selected['state_db_path'], new_name=new_filename)
            print(f"\nYou can now analyze this file by running:\npython extract_prompts.py --file {new_filename}")
            
            another = input("\nDo you want to copy another workspace? (y/n): ")
            if another.lower() != 'y':
                break
                
        except ValueError:
            print("Please enter a valid number.")
        except Exception as e:
            print(f"Error: {str(e)}")

def list_mode():
    """Just list all workspaces without copying any files."""
    workspaces = find_workspace_files()
    
    if not workspaces:
        print("No workspaces found.")
        return
    
    print(f"\nFound {len(workspaces)} workspace folders:")
    print("-" * 80)
    print(f"{'#':<3} {'Workspace Name':<30} {'Has DB':<8} {'Hash'}")
    print("-" * 80)
    
    for i, workspace in enumerate(workspaces):
        workspace_name = workspace['name'] or 'Unknown'
        has_db = "✓" if workspace['has_state_db'] else "✗"
        print(f"{i+1:<3} {workspace_name:<30} {has_db:<8} {workspace['hash']}")
    
    print("-" * 80)
    
    # Print summary of how to use the tool
    print("\nTo copy a workspace database file, run one of these commands:")
    print(f"  python find_workspace.py --copy \"First Project\"")
    print(f"  python find_workspace.py --copy 2")
    print("\nOr run in interactive mode:")
    print(f"  python find_workspace.py")

def copy_specific_workspace(workspace_name_or_index):
    """Copy a specific workspace by name or index."""
    workspaces = find_workspace_files()
    
    if not workspaces:
        print("No workspaces found.")
        return
    
    selected = None
    
    # Try to interpret as an index
    try:
        idx = int(workspace_name_or_index) - 1
        if 0 <= idx < len(workspaces):
            selected = workspaces[idx]
    except ValueError:
        # Try to interpret as a name
        for workspace in workspaces:
            if workspace['name'] and workspace_name_or_index.lower() in workspace['name'].lower():
                selected = workspace
                break
    
    if not selected:
        print(f"Could not find workspace matching '{workspace_name_or_index}'.")
        list_mode()  # Show available workspaces
        return
    
    if not selected['has_state_db']:
        print(f"The selected workspace ({selected['name']}) does not have a state.vscdb file.")
        return
    
    workspace_name = selected['name'] or 'unknown'
    safe_name = re.sub(r'[^\w\s-]', '', workspace_name).strip().replace(' ', '_')
    new_filename = f"{safe_name}_state.vscdb"
    
    copy_state_db(selected['state_db_path'], new_name=new_filename)
    print(f"\nYou can now analyze this file by running:\npython extract_prompts.py --file {new_filename}")

def main():
    """Main function to find and process workspaces."""
    parser = argparse.ArgumentParser(description='Find and manage Cursor workspace files')
    
    # Create a mutually exclusive group for the different modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--list', '-l', action='store_true', 
                       help='List all workspaces without copying any files')
    group.add_argument('--copy', '-c', metavar='WORKSPACE', 
                       help='Copy a specific workspace (specify name or number)')
    group.add_argument('--interactive', '-i', action='store_true',
                       help='Run in interactive mode (default)')
    
    args = parser.parse_args()
    
    if args.list:
        list_mode()
    elif args.copy:
        copy_specific_workspace(args.copy)
    else:
        # Default to interactive mode
        interactive_mode()

if __name__ == "__main__":
    main() 