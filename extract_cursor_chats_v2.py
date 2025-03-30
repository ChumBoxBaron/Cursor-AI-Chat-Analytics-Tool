import os
import sqlite3
import json
import re
from datetime import datetime
import glob

def find_cursor_directories():
    """Find all potential Cursor data directories."""
    potential_dirs = []
    
    # Windows paths
    appdata = os.environ.get('APPDATA')
    localappdata = os.environ.get('LOCALAPPDATA')
    userprofile = os.environ.get('USERPROFILE')
    
    if appdata:
        # Main workspace storage
        potential_dirs.append(os.path.join(appdata, 'Cursor', 'User', 'workspaceStorage'))
        potential_dirs.append(os.path.join(appdata, 'Cursor', 'User Data', 'Default', 'Local Storage', 'leveldb'))
        potential_dirs.append(os.path.join(appdata, 'Cursor'))
    
    if localappdata:
        potential_dirs.append(os.path.join(localappdata, 'Cursor'))
    
    if userprofile:
        potential_dirs.append(os.path.join(userprofile, '.cursor'))
    
    # Filter to only directories that exist
    existing_dirs = [d for d in potential_dirs if os.path.exists(d)]
    return existing_dirs

def find_cursor_files(base_dirs):
    """Find all potential files that might contain Cursor chat data."""
    potential_files = []
    
    for base_dir in base_dirs:
        # Look for SQLite databases
        for pattern in ['**/*.vscdb', '**/*.db', '**/*.sqlite']:
            db_files = glob.glob(os.path.join(base_dir, pattern), recursive=True)
            potential_files.extend(db_files)
        
        # Look for JSON files that might contain chat data
        json_files = glob.glob(os.path.join(base_dir, '**/*.json'), recursive=True)
        potential_files.extend(json_files)
        
        # Look for LevelDB files
        ldb_files = glob.glob(os.path.join(base_dir, '**/*.ldb'), recursive=True)
        potential_files.extend(ldb_files)
    
    return potential_files

def extract_data_from_sqlite(db_file):
    """Extract potential chat data from a SQLite database file."""
    results = []
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Common queries based on known Cursor structures
        queries = [
            "SELECT value FROM ItemTable WHERE [key] IN ('workbench.panel.aichat.view.aichat.chatdata');",
            "SELECT value FROM ItemTable WHERE [key] LIKE '%chat%' OR [key] LIKE '%ai%';",
            "SELECT value FROM ItemTable WHERE [key] LIKE '%prompt%';",
            "SELECT value FROM ItemTable WHERE [key] LIKE '%cursor%';",
            "SELECT value FROM ItemTable WHERE [key] LIKE '%history%';",
            "SELECT value FROM ItemTable WHERE [key] LIKE '%message%';",
        ]
        
        # Try each query
        for query in queries:
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        results.append(row[0])
            except:
                # If query fails (e.g., table doesn't exist), continue to next query
                continue
                
        # If no results, try to get all data from each table
        if not results:
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 1000;")
                    columns = [description[0] for description in cursor.description]
                    
                    # Look for columns that might contain chat data
                    potential_columns = [col for col in columns if any(keyword in col.lower() for keyword in ['key', 'value', 'data', 'content', 'message', 'chat', 'ai', 'text'])]
                    
                    if potential_columns:
                        column_list = ', '.join(potential_columns)
                        cursor.execute(f"SELECT {column_list} FROM {table_name} LIMIT 1000;")
                        rows = cursor.fetchall()
                        for row in rows:
                            for col_value in row:
                                if col_value and isinstance(col_value, str) and ('{' in col_value or '[' in col_value):
                                    results.append(col_value)
                except:
                    continue
    except Exception as e:
        print(f"Error accessing database {db_file}: {str(e)}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    
    return results

def extract_data_from_json(json_file):
    """Extract potential chat data from a JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if the file contains chat-related keywords
        chat_keywords = ['chat', 'message', 'conversation', 'prompt', 'assistant', 'user', 'ai', 'cursor']
        if not any(keyword in content.lower() for keyword in chat_keywords):
            return []
            
        # Try to parse as JSON
        data = json.loads(content)
        return [content]
    except:
        return []

def count_words(text):
    """Count the number of words in text."""
    if not text or not isinstance(text, str):
        return 0
    return len(re.findall(r'\b\w+\b', text))

def is_valid_chat_data(data_str):
    """Check if a string looks like it contains chat data."""
    # Common patterns in chat data
    patterns = [
        r'"role"\s*:\s*"user"',
        r'"role"\s*:\s*"assistant"',
        r'"content"\s*:',
        r'"messages"\s*:',
        r'"prompt"\s*:',
        r'"response"\s*:',
        r'"chat"',
        r'"tabs"'
    ]
    
    return any(re.search(pattern, data_str) for pattern in patterns)

def try_parse_json(data_str):
    """Try to parse a string as JSON, handling various formats."""
    # Try direct JSON parsing
    try:
        return json.loads(data_str)
    except:
        pass
    
    # Try to extract JSON objects from the string
    try:
        # Look for objects like {...}
        object_match = re.search(r'(\{.*\})', data_str)
        if object_match:
            return json.loads(object_match.group(1))
        
        # Look for arrays like [...]
        array_match = re.search(r'(\[.*\])', data_str)
        if array_match:
            return json.loads(array_match.group(1))
    except:
        pass
    
    return None

def format_potential_chat_data(data_str):
    """Try to extract and format potential chat data from a string."""
    if not is_valid_chat_data(data_str):
        return []
    
    parsed_data = try_parse_json(data_str)
    if not parsed_data:
        return []
    
    formatted_chats = []
    chat_title = "Extracted Chat"
    
    # Format 1: Tabs format (newer versions)
    if isinstance(parsed_data, dict) and 'tabs' in parsed_data:
        for tab_id, tab in parsed_data['tabs'].items():
            title = tab.get('title', 'Untitled Chat')
            messages = tab.get('messages', [])
            
            if messages:
                formatted_chat = format_messages(title, messages)
                formatted_chats.append((title, formatted_chat))
    
    # Format 2: Messages array directly
    elif isinstance(parsed_data, list) and parsed_data and 'role' in parsed_data[0]:
        formatted_chat = format_messages(chat_title, parsed_data)
        formatted_chats.append((chat_title, formatted_chat))
    
    # Format 3: Object with messages array
    elif isinstance(parsed_data, dict) and 'messages' in parsed_data:
        title = parsed_data.get('title', chat_title)
        messages = parsed_data['messages']
        formatted_chat = format_messages(title, messages)
        formatted_chats.append((title, formatted_chat))
    
    return formatted_chats

def format_messages(title, messages):
    """Format a list of messages into a readable format with stats."""
    formatted_chat = f"# {title}\n\n"
    
    user_word_count = 0
    ai_word_count = 0
    user_messages = 0
    ai_messages = 0
    
    for msg in messages:
        if not isinstance(msg, dict):
            continue
            
        role = msg.get('role', '')
        content = msg.get('content', '')
        
        if isinstance(content, list):  # Handle content arrays (newer formats)
            content = "\n".join([str(item) for item in content])
        
        if role == 'user':
            formatted_chat += f"## User\n{content}\n\n"
            user_word_count += count_words(content)
            user_messages += 1
        elif role == 'assistant':
            formatted_chat += f"## Assistant\n{content}\n\n"
            ai_word_count += count_words(content)
            ai_messages += 1
    
    # Add statistics
    formatted_chat += f"## Stats\n"
    formatted_chat += f"- Total messages: {len(messages)}\n"
    formatted_chat += f"- User messages: {user_messages}\n"
    formatted_chat += f"- User word count: {user_word_count}\n"
    formatted_chat += f"- AI messages: {ai_messages}\n"
    formatted_chat += f"- AI word count: {ai_word_count}\n"
    
    return formatted_chat

def save_chats(chats, output_dir="extracted_chats"):
    """Save formatted chats to files."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_count = 0
    
    for i, (title, content) in enumerate(chats):
        # Create a safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        if not safe_title:
            safe_title = f"chat_{i}"
        
        filename = f"{safe_title}_{timestamp}_{i}.md"
        filepath = os.path.join(output_dir, filename)
        
        # Check if the content is substantial (more than just a title and headers)
        if count_words(content) > 10:  # Arbitrary threshold
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Saved chat to {filepath}")
            saved_count += 1
    
    return saved_count

def extract_cursor_chats():
    """Main function to extract and save Cursor chats."""
    print("Searching for Cursor data directories...")
    cursor_dirs = find_cursor_directories()
    
    if not cursor_dirs:
        print("No Cursor data directories found.")
        return
    
    print(f"Found {len(cursor_dirs)} Cursor data directories:")
    for directory in cursor_dirs:
        print(f"  - {directory}")
    
    print("\nSearching for potential chat data files...")
    potential_files = find_cursor_files(cursor_dirs)
    
    if not potential_files:
        print("No potential chat data files found.")
        return
    
    print(f"Found {len(potential_files)} potential files to check.")
    
    total_files_processed = 0
    total_chats_extracted = 0
    
    # Process SQLite files first (more likely to contain structured data)
    sqlite_files = [f for f in potential_files if f.endswith(('.vscdb', '.db', '.sqlite'))]
    print(f"\nProcessing {len(sqlite_files)} SQLite database files...")
    
    for i, db_file in enumerate(sqlite_files):
        print(f"\nProcessing file {i+1}/{len(sqlite_files)}: {db_file}")
        
        extracted_data = extract_data_from_sqlite(db_file)
        if not extracted_data:
            print("  - No chat data found in this file.")
            continue
        
        print(f"  - Found {len(extracted_data)} potential chat data entries")
        
        # Process each extracted data string
        for j, data_str in enumerate(extracted_data):
            print(f"  - Processing entry {j+1}/{len(extracted_data)}")
            
            formatted_chats = format_potential_chat_data(data_str)
            if formatted_chats:
                saved_count = save_chats(formatted_chats)
                total_chats_extracted += saved_count
                print(f"    - Extracted {len(formatted_chats)} chats, saved {saved_count} to files")
        
        total_files_processed += 1
    
    # Process JSON files
    json_files = [f for f in potential_files if f.endswith('.json')]
    print(f"\nProcessing {len(json_files)} JSON files...")
    
    for i, json_file in enumerate(json_files):
        print(f"\nProcessing file {i+1}/{len(json_files)}: {json_file}")
        
        extracted_data = extract_data_from_json(json_file)
        if not extracted_data:
            continue
        
        # Process each extracted data string
        for data_str in extracted_data:
            formatted_chats = format_potential_chat_data(data_str)
            if formatted_chats:
                saved_count = save_chats(formatted_chats)
                total_chats_extracted += saved_count
                print(f"  - Extracted {len(formatted_chats)} chats, saved {saved_count} to files")
        
        total_files_processed += 1
    
    print("\nExtraction complete!")
    print(f"Total files processed: {total_files_processed}")
    print(f"Total chats extracted: {total_chats_extracted}")
    print(f"Saved chats can be found in the 'extracted_chats' directory")

if __name__ == "__main__":
    extract_cursor_chats() 