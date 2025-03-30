import os
import sqlite3
import json
import re
from datetime import datetime

def extract_chat_data(db_file):
    """Extract chat data from a state.vscdb file."""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Try the main query for chat data
        cursor.execute("SELECT [key], value FROM ItemTable WHERE [key] LIKE '%chat%' OR [key] LIKE '%ai%';")
        rows = cursor.fetchall()
        
        if not rows:
            print("No chat data found using primary query.")
            print("Trying additional queries...")
            
            # Try alternative queries
            queries = [
                "SELECT [key], value FROM ItemTable WHERE [key] LIKE '%prompt%';",
                "SELECT [key], value FROM ItemTable WHERE [key] LIKE '%cursor%';",
                "SELECT [key], value FROM ItemTable WHERE [key] LIKE '%history%';",
                "SELECT [key], value FROM ItemTable WHERE [key] LIKE '%message%';",
                "SELECT * FROM ItemTable LIMIT 20;"  # Just get some sample data to understand structure
            ]
            
            results = []
            for query in queries:
                try:
                    print(f"Trying query: {query}")
                    cursor.execute(query)
                    query_rows = cursor.fetchall()
                    if query_rows:
                        print(f"Found {len(query_rows)} rows with this query.")
                        results.extend(query_rows)
                except Exception as e:
                    print(f"Error with query: {str(e)}")
            
            return results
        
        return rows
    except Exception as e:
        print(f"Error accessing database: {str(e)}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def count_words(text):
    """Count the number of words in text."""
    if not text or not isinstance(text, str):
        return 0
    return len(re.findall(r'\b\w+\b', text))

def try_parse_json(data_str):
    """Try to parse a string as JSON."""
    try:
        return json.loads(data_str)
    except:
        return None

def format_chat_data(parsed_data, key_name="Unknown"):
    """Format chat data from parsed JSON."""
    if not parsed_data:
        return None
    
    # Different possible formats based on Cursor versions
    
    # Format 1: Tabs format (newer versions)
    if isinstance(parsed_data, dict) and 'tabs' in parsed_data:
        chats = []
        for tab_id, tab in parsed_data['tabs'].items():
            chat_title = tab.get('title', f'Chat {tab_id}')
            messages = tab.get('messages', [])
            
            if messages:
                formatted_chat = f"# {chat_title}\n\n"
                
                user_word_count = 0
                ai_word_count = 0
                user_messages = 0
                ai_messages = 0
                
                for msg in messages:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
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
                
                chats.append((chat_title, formatted_chat, {
                    'user_messages': user_messages,
                    'user_words': user_word_count,
                    'ai_messages': ai_messages,
                    'ai_words': ai_word_count,
                    'total_messages': len(messages)
                }))
        
        return chats
    
    # Format 2: Array format (older versions)
    elif isinstance(parsed_data, list) and parsed_data and isinstance(parsed_data[0], dict) and 'role' in parsed_data[0]:
        chat_title = f"Chat from {key_name}"
        formatted_chat = f"# {chat_title}\n\n"
        
        user_word_count = 0
        ai_word_count = 0
        user_messages = 0
        ai_messages = 0
        
        for msg in parsed_data:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
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
        formatted_chat += f"- Total messages: {len(parsed_data)}\n"
        formatted_chat += f"- User messages: {user_messages}\n"
        formatted_chat += f"- User word count: {user_word_count}\n"
        formatted_chat += f"- AI messages: {ai_messages}\n"
        formatted_chat += f"- AI word count: {ai_word_count}\n"
        
        return [(chat_title, formatted_chat, {
            'user_messages': user_messages,
            'user_words': user_word_count,
            'ai_messages': ai_messages,
            'ai_words': ai_word_count,
            'total_messages': len(parsed_data)
        })]
    
    return None

def save_chats(chats, output_dir="extracted_chats"):
    """Save formatted chats to files."""
    if not chats:
        return 0
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_count = 0
    
    for i, (title, content, _) in enumerate(chats):
        # Create a safe filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        if not safe_title:
            safe_title = f"chat_{i}"
        
        filename = f"{safe_title}_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Saved chat to {filepath}")
        saved_count += 1
    
    return saved_count

def process_file(file_path):
    """Process a specific state.vscdb file."""
    print(f"Processing file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    extracted_data = extract_chat_data(file_path)
    if not extracted_data:
        print("No chat data found in this file.")
        return
    
    print(f"Found {len(extracted_data)} potential chat data entries")
    
    all_stats = {
        'total_chats': 0,
        'total_user_messages': 0,
        'total_user_words': 0,
        'total_ai_messages': 0,
        'total_ai_words': 0
    }
    
    # Process each extracted data string
    total_extracted = 0
    for i, row in enumerate(extracted_data):
        key = row[0] if len(row) > 1 else f"Entry_{i}"
        value = row[1] if len(row) > 1 else row[0]
        
        if not isinstance(value, str):
            continue
            
        print(f"\nProcessing entry {i+1}/{len(extracted_data)}: {key}")
        
        # Try to parse the data
        parsed_data = try_parse_json(value)
        if not parsed_data:
            print(f"  - Could not parse as JSON: {value[:100]}...")
            continue
        
        # Format the chat data
        formatted_chats = format_chat_data(parsed_data, key)
        if not formatted_chats:
            print("  - Could not format as chat data")
            continue
        
        # Save the chats
        saved_count = save_chats(formatted_chats)
        total_extracted += saved_count
        
        print(f"  - Extracted {len(formatted_chats)} chats, saved {saved_count}")
        
        # Update stats
        for _, _, stats in formatted_chats:
            all_stats['total_chats'] += 1
            all_stats['total_user_messages'] += stats['user_messages']
            all_stats['total_user_words'] += stats['user_words']
            all_stats['total_ai_messages'] += stats['ai_messages']
            all_stats['total_ai_words'] += stats['ai_words']
    
    # Print final stats
    print("\nExtraction complete!")
    print(f"Total chats extracted: {all_stats['total_chats']}")
    print(f"Total user messages: {all_stats['total_user_messages']}")
    print(f"Total user words: {all_stats['total_user_words']}")
    print(f"Total AI messages: {all_stats['total_ai_messages']}")
    print(f"Total AI words: {all_stats['total_ai_words']}")
    
    if total_extracted == 0:
        print("\nCould not extract any chats from this file.")
        print("The data format might be different than expected.")
        print("Dumping some sample data for debug purposes...")
        
        for i, row in enumerate(extracted_data[:3]):
            key = row[0] if len(row) > 1 else f"Entry_{i}"
            value = row[1] if len(row) > 1 else row[0]
            print(f"\nKey: {key}")
            print(f"Value (first 500 chars): {str(value)[:500]}")

if __name__ == "__main__":
    db_file = "state.vscdb"  # The file in our current directory
    process_file(db_file) 