import sqlite3
import json
import os

def dump_database_structure(db_file):
    """Dump the structure of the database to understand what's in it."""
    if not os.path.exists(db_file):
        print(f"File not found: {db_file}")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Database contains {len(tables)} tables:")
        for i, table in enumerate(tables):
            table_name = table[0]
            print(f"  {i+1}. {table_name}")
            
            # Get column info
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print(f"    Columns: {', '.join(col[1] for col in columns)}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"    Row count: {count}")
        
        # For ItemTable, which we expect to contain chat data, dump all keys
        if any(table[0] == 'ItemTable' for table in tables):
            print("\nDumping all keys in ItemTable:")
            cursor.execute("SELECT [key] FROM ItemTable;")
            keys = cursor.fetchall()
            
            for i, key in enumerate(keys):
                print(f"  {i+1}. {key[0]}")
            
            # Let's check if there's a specific key for chat data
            chat_keys = ["workbench.panel.aichat.view.aichat.chatdata", 
                         "aiService.prompts", 
                         "chat.history"]
            
            for chat_key in chat_keys:
                print(f"\nChecking for key: {chat_key}")
                cursor.execute(f"SELECT value FROM ItemTable WHERE [key] = ?;", (chat_key,))
                row = cursor.fetchone()
                
                if row:
                    value = row[0]
                    print(f"  Found! Value preview: {str(value)[:100]}...")
                    
                    # Try to parse as JSON and check structure
                    try:
                        data = json.loads(value)
                        if isinstance(data, dict):
                            print(f"  JSON structure - keys: {', '.join(data.keys())}")
                        elif isinstance(data, list):
                            print(f"  JSON structure - array with {len(data)} items")
                            if data and isinstance(data[0], dict):
                                print(f"  First item keys: {', '.join(data[0].keys())}")
                    except:
                        print("  Could not parse as JSON")
                else:
                    print("  Not found")
            
            # Now try to find any key that might be related to chat
            print("\nSearching for potential chat-related keys:")
            cursor.execute("SELECT [key], value FROM ItemTable WHERE [key] LIKE '%chat%' OR [key] LIKE '%ai%' OR [key] LIKE '%prompt%';")
            rows = cursor.fetchall()
            
            for i, row in enumerate(rows):
                key, value = row
                print(f"\n{i+1}. Key: {key}")
                print(f"   Value preview: {str(value)[:150]}...")
    except Exception as e:
        print(f"Error accessing database: {str(e)}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    db_file = "state.vscdb"  # The file in our current directory
    dump_database_structure(db_file) 