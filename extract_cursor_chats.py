import os
import sqlite3
import json
from datetime import datetime
import re

def find_workspace_storage():
    """Find the Cursor workspace storage directory."""
    appdata = os.environ.get('APPDATA')
    if not appdata:
        print("APPDATA environment variable not found.")
        return None
    
    workspace_storage = os.path.join(appdata, 'Cursor', 'User', 'workspaceStorage')
    if not os.path.exists(workspace_storage):
        print(f"Workspace storage directory not found at: {workspace_storage}")
        return None
    
    return workspace_storage

def find_vscdb_files(workspace_storage):
    """Find all state.vscdb files in the workspace storage directory."""
    vscdb_files = []
    
    for root, dirs, files in os.walk(workspace_storage):
        for file in files:
            if file == 'state.vscdb':
                vscdb_files.append(os.path.join(root, file))
    
    return vscdb_files

def extract_chat_data(db_file):
    """Extract chat data from a state.vscdb file."""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Try the main query for chat data
        cursor.execute("SELECT value FROM ItemTable WHERE [key] IN ('workbench.panel.aichat.view.aichat.chatdata');")
        chat_data = cursor.fetchone()
        
        # If no results, try alternative keys
        if not chat_data:
            cursor.execute("SELECT value FROM ItemTable WHERE [key] LIKE '%chat%' OR [key] LIKE '%ai%';")
            chat_data = cursor.fetchall()
            
            if chat_data:
                print(f"Found {len(chat_data)} potential chat entries using alternative query.")
                return chat_data
        else:
            return chat_data[0] if chat_data else None
    except Exception as e:
        print(f"Error accessing database {db_file}: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def count_words(text):
    """Count the number of words in text."""
    return len(re.findall(r'\b\w+\b', text))

def format_chat_data(chat_json):
    """Format chat data from JSON."""
    try:
        # Try to parse the JSON
        data = json.loads(chat_json)
        
        # Different possible formats based on Cursor versions
        formatted_chats = []
        
        # Format 1: Tabs format (newer versions)
        if isinstance(data, dict) and 'tabs' in data:
            for tab_id, tab in data['tabs'].items():
                chat_title = tab.get('title', 'Untitled Chat')
                messages = tab.get('messages', [])
                
                if messages:
                    formatted_chat = f"# {chat_title}\n\n"
                    
                    user_word_count = 0
                    ai_word_count = 0
                    
                    for msg in messages:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        
                        if role == 'user':
                            formatted_chat += f"## User\n{content}\n\n"
                            user_word_count += count_words(content)
                        elif role == 'assistant':
                            formatted_chat += f"## Assistant\n{content}\n\n"
                            ai_word_count += count_words(content)
                    
                    # Add statistics
                    formatted_chat += f"## Stats\n"
                    formatted_chat += f"- Total messages: {len(messages)}\n"
                    formatted_chat += f"- User word count: {user_word_count}\n"
                    formatted_chat += f"- AI word count: {ai_word_count}\n"
                    
                    formatted_chats.append((chat_title, formatted_chat))
        
        # Format 2: Array format (older versions)
        elif isinstance(data, list):
            chat_title = "Chat History"
            formatted_chat = f"# {chat_title}\n\n"
            
            user_word_count = 0
            ai_word_count = 0
            
            for msg in data:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                
                if role == 'user':
                    formatted_chat += f"## User\n{content}\n\n"
                    user_word_count += count_words(content)
                elif role == 'assistant':
                    formatted_chat += f"## Assistant\n{content}\n\n"
                    ai_word_count += count_words(content)
            
            # Add statistics
            formatted_chat += f"## Stats\n"
            formatted_chat += f"- Total messages: {len(data)}\n"
            formatted_chat += f"- User word count: {user_word_count}\n"
            formatted_chat += f"- AI word count: {ai_word_count}\n"
            
            formatted_chats.append((chat_title, formatted_chat))
        
        return formatted_chats
    except json.JSONDecodeError:
        print("Failed to parse JSON data")
        return []
    except Exception as e:
        print(f"Error formatting chat data: {str(e)}")
        return []

def save_chats(chats, output_dir="extracted_chats"):
    """Save formatted chats to files."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, (title, content) in enumerate(chats):
        # Create a safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        if not safe_title:
            safe_title = f"chat_{i}"
        
        filename = f"{safe_title}_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved chat to {filepath}")

def extract_all_chats():
    """Main function to extract and save all chats."""
    print("Searching for Cursor workspace storage...")
    workspace_storage = find_workspace_storage()
    
    if not workspace_storage:
        return
    
    print(f"Found workspace storage at: {workspace_storage}")
    
    vscdb_files = find_vscdb_files(workspace_storage)
    
    if not vscdb_files:
        print("No state.vscdb files found.")
        return
    
    print(f"Found {len(vscdb_files)} state.vscdb files.")
    
    all_stats = {
        "total_workspaces": len(vscdb_files),
        "total_chats": 0,
        "total_user_words": 0,
        "total_ai_words": 0
    }
    
    for i, db_file in enumerate(vscdb_files):
        print(f"\nProcessing file {i+1}/{len(vscdb_files)}: {db_file}")
        
        chat_data = extract_chat_data(db_file)
        if not chat_data:
            print("No chat data found in this file.")
            continue
        
        if isinstance(chat_data, list):
            # Multiple potential chat entries
            for j, entry in enumerate(chat_data):
                print(f"Processing potential chat entry {j+1}/{len(chat_data)}")
                try:
                    formatted_chats = format_chat_data(entry[0])
                    if formatted_chats:
                        all_stats["total_chats"] += len(formatted_chats)
                        save_chats(formatted_chats)
                except Exception as e:
                    print(f"Error processing entry: {str(e)}")
        else:
            # Single chat entry
            formatted_chats = format_chat_data(chat_data)
            if formatted_chats:
                all_stats["total_chats"] += len(formatted_chats)
                save_chats(formatted_chats)
    
    print("\nExtraction complete!")
    print(f"Total workspaces processed: {all_stats['total_workspaces']}")
    print(f"Total chats extracted: {all_stats['total_chats']}")

if __name__ == "__main__":
    extract_all_chats() 