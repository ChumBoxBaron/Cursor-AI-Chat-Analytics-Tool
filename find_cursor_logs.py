import os
import glob
import json
from pathlib import Path

def find_cursor_logs():
    """Search for Cursor chat log files in common locations"""
    
    # Common locations to check
    potential_paths = [
        os.path.join(os.environ.get('APPDATA', ''), 'Cursor', 'User Data', 'Default', 'Local Storage', 'leveldb'),
        os.path.join(os.environ.get('USERPROFILE', ''), '.cursor'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Cursor'),
    ]
    
    found_files = []
    
    for path in potential_paths:
        if os.path.exists(path):
            print(f"Found directory: {path}")
            # Look for JSON files or LevelDB files that might contain chat logs
            for ext in ['*.json', '*.ldb', '*.log']:
                matches = glob.glob(os.path.join(path, '**', ext), recursive=True)
                if matches:
                    found_files.extend(matches)
                    print(f"  - Found {len(matches)} {ext} files")
    
    return found_files

def analyze_file(filepath):
    """Try to analyze a file to determine if it contains chat logs"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Look for chat indicators in the content
            chat_indicators = ['prompt', 'message', 'assistant', 'user', 'chat', 'conversation']
            hits = sum(1 for indicator in chat_indicators if indicator in content.lower())
            
            if hits >= 2:  # If at least 2 chat indicators are found
                print(f"\nPotential chat log found in: {filepath}")
                print(f"  - Contains {hits}/6 chat indicators")
                try:
                    # Try to parse as JSON
                    json_data = json.loads(content)
                    print("  - Valid JSON format")
                    return True
                except json.JSONDecodeError:
                    print("  - Not in JSON format or incomplete JSON")
                    # Try to extract JSON-like structures
                    if '{"' in content and '"}' in content:
                        print("  - Contains JSON-like structures")
                        return True
    except Exception as e:
        print(f"Error analyzing {filepath}: {str(e)}")
    
    return False

if __name__ == "__main__":
    print("Searching for Cursor chat logs...")
    log_files = find_cursor_logs()
    
    if not log_files:
        print("\nNo potential log files found in common locations.")
        print("You might need to check other directories or consider alternative approaches.")
    else:
        print(f"\nFound {len(log_files)} potential files to analyze.")
        print("Analyzing files for chat content...")
        
        chat_logs = []
        for file in log_files[:20]:  # Limit to first 20 files to avoid too much processing
            if analyze_file(file):
                chat_logs.append(file)
        
        if chat_logs:
            print(f"\nFound {len(chat_logs)} potential chat log files!")
            print("You can examine these files for further analysis.")
        else:
            print("\nNo files containing chat logs were identified.")
            print("Consider creating a custom tracking solution instead.") 