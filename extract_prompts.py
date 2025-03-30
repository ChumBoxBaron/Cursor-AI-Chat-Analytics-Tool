import sqlite3
import json
import os
import re
import argparse
from datetime import datetime

def count_words(text):
    """Count the number of words in text."""
    if not text or not isinstance(text, str):
        return 0
    return len(re.findall(r'\b\w+\b', text))

def extract_prompts(db_file):
    """Extract and analyze prompts from the database."""
    if not os.path.exists(db_file):
        print(f"File not found: {db_file}")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get the prompts data
        cursor.execute("SELECT value FROM ItemTable WHERE [key] = 'aiService.prompts';")
        row = cursor.fetchone()
        
        if not row:
            print("No prompt data found.")
            return
        
        # Parse the JSON data
        prompts_data = json.loads(row[0])
        
        if not prompts_data:
            print("No prompts found in the data.")
            return
        
        print(f"Found {len(prompts_data)} prompts!")
        
        # Analyze the data
        total_words = 0
        command_types = {}
        
        for i, prompt in enumerate(prompts_data):
            prompt_text = prompt.get('text', '')
            command_type = prompt.get('commandType', 'unknown')
            
            # Count command types
            command_types[command_type] = command_types.get(command_type, 0) + 1
            
            # Count words
            word_count = count_words(prompt_text)
            total_words += word_count
        
        # Print statistics
        print("\nPrompt Statistics:")
        print(f"Total prompts: {len(prompts_data)}")
        print(f"Total words across all prompts: {total_words}")
        print(f"Average words per prompt: {total_words / len(prompts_data):.1f}")
        
        print("\nCommand Types:")
        for cmd_type, count in command_types.items():
            print(f"  Type {cmd_type}: {count} prompts")
        
        # Save the prompts to a file
        save_prompts_to_file(prompts_data)
        
    except Exception as e:
        print(f"Error extracting prompts: {str(e)}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def save_prompts_to_file(prompts_data):
    """Save the prompts to a markdown file."""
    output_dir = "extracted_prompts"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"cursor_prompts_{timestamp}.md")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# Cursor Prompts History\n\n")
        f.write("| # | Command Type | Word Count | Prompt |\n")
        f.write("|---|-------------|------------|--------|\n")
        
        for i, prompt in enumerate(prompts_data):
            prompt_text = prompt.get('text', '')
            command_type = prompt.get('commandType', 'unknown')
            word_count = count_words(prompt_text)
            
            # Truncate very long prompts for table readability
            display_text = prompt_text
            if len(display_text) > 100:
                display_text = display_text[:97] + "..."
            
            # Escape pipe characters in markdown table
            display_text = display_text.replace('|', '\\|')
            
            f.write(f"| {i+1} | {command_type} | {word_count} | {display_text} |\n")
        
        # Add statistics at the end
        f.write("\n\n## Statistics\n\n")
        f.write(f"- Total prompts: {len(prompts_data)}\n")
        f.write(f"- Total words: {sum(count_words(p.get('text', '')) for p in prompts_data)}\n")
        f.write(f"- Average words per prompt: {sum(count_words(p.get('text', '')) for p in prompts_data) / len(prompts_data):.1f}\n")
    
    print(f"\nSaved prompts to {filepath}")
    
    # Also save the full prompts to a text file (without truncation)
    txt_filepath = os.path.join(output_dir, f"cursor_prompts_full_{timestamp}.txt")
    
    with open(txt_filepath, 'w', encoding='utf-8') as f:
        for i, prompt in enumerate(prompts_data):
            prompt_text = prompt.get('text', '')
            command_type = prompt.get('commandType', 'unknown')
            
            f.write(f"Prompt #{i+1} (Type {command_type}):\n")
            f.write(f"{prompt_text}\n")
            f.write("-" * 80 + "\n\n")
    
    print(f"Saved full prompts to {txt_filepath}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract and analyze prompts from Cursor state.vscdb files')
    parser.add_argument('--file', '-f', type=str, default="state.vscdb", 
                        help='Path to the state.vscdb file (default: state.vscdb)')
    
    args = parser.parse_args()
    extract_prompts(args.file) 