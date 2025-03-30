import os
import json
import sqlite3
import re
import argparse
import shutil
from datetime import datetime
import time
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict, Counter
from textblob import TextBlob  # for sentiment analysis

# Import from our existing scripts
try:
    from find_workspace import find_workspace_files, copy_state_db
    from extract_prompts import count_words
except ImportError:
    print("Warning: Unable to import from existing scripts. Some functionality may be limited.")
    
    # Define minimal versions of the functions we need
    def find_workspace_files():
        """Placeholder for the imported function"""
        print("Error: find_workspace module not available")
        return []
        
    def copy_state_db(state_db_path, output_dir='.', new_name=None):
        """Placeholder for the imported function"""
        print("Error: find_workspace module not available")
        return False
        
    def count_words(text):
        """Count the number of words in text."""
        if not text or not isinstance(text, str):
            return 0
        return len(re.findall(r'\b\w+\b', text))

class WorkspaceAnalyzer:
    """Class to analyze prompt data from multiple workspaces"""
    
    def __init__(self, output_dir="analysis_results"):
        self.output_dir = output_dir
        self.workspaces = []
        self.all_prompts = []  # For aggregated analysis
        self.workspace_prompts = {}  # Prompts organized by workspace
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def add_workspace(self, workspace_info, db_path):
        """Add a workspace to be analyzed"""
        self.workspaces.append({
            'info': workspace_info,
            'db_path': db_path,
            'prompts': []
        })
    
    def extract_data_from_db(self, db_path):
        """Extract prompt data from a database file"""
        prompts = []
        responses = []
        
        if not os.path.exists(db_path):
            print(f"Database file not found: {db_path}")
            return prompts, responses
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Extract prompts
            cursor.execute("SELECT value FROM ItemTable WHERE [key] = 'aiService.prompts';")
            row = cursor.fetchone()
            
            if row:
                prompts = json.loads(row[0])
            else:
                print("No prompt data found.")
            
            # Try to extract chat responses
            # This is experimental and may not work in all versions of Cursor
            try:
                cursor.execute("SELECT value FROM ItemTable WHERE [key] LIKE 'chat%' OR [key] LIKE '%conversation%';")
                chats_rows = cursor.fetchall()
                
                if chats_rows:
                    for row in chats_rows:
                        try:
                            chat_data = json.loads(row[0])
                            if isinstance(chat_data, list):
                                for item in chat_data:
                                    if isinstance(item, dict) and 'response' in item:
                                        responses.append(item)
                        except:
                            pass  # Skip invalid JSON
            except:
                print("Unable to extract chat responses")
                
        except Exception as e:
            print(f"Error extracting data from database: {str(e)}")
        finally:
            if 'conn' in locals() and conn:
                conn.close()
                
        return prompts, responses
    
    def process_workspace(self, index):
        """Process a single workspace"""
        workspace = self.workspaces[index]
        name = workspace['info']['name'] or f"Workspace_{index+1}"
        
        print(f"\nProcessing workspace: {name}")
        prompts, responses = self.extract_data_from_db(workspace['db_path'])
        
        if prompts:
            print(f"  Found {len(prompts)} prompts")
            workspace['prompts'] = prompts
            self.workspace_prompts[name] = prompts
            self.all_prompts.extend(prompts)
        else:
            print("  No prompts found")
            
        if responses:
            print(f"  Found {len(responses)} responses")
            workspace['responses'] = responses
        else:
            print("  No responses found")
    
    def process_all_workspaces(self):
        """Process all workspaces that have been added"""
        for i in range(len(self.workspaces)):
            self.process_workspace(i)
    
    def calculate_prompt_stats(self, prompts):
        """Calculate statistics for a set of prompts"""
        if not prompts:
            return {}
            
        word_counts = [count_words(p.get('text', '')) for p in prompts]
        char_counts = [len(p.get('text', '')) for p in prompts]
        
        # Calculate timestamps if available
        timestamps = []
        for p in prompts:
            if 'timestamp' in p:
                timestamps.append(p['timestamp'])
        
        # Calculate time differences between prompts if we have timestamps
        time_diffs = []
        if len(timestamps) > 1:
            sorted_timestamps = sorted(timestamps)
            for i in range(1, len(sorted_timestamps)):
                time_diffs.append(sorted_timestamps[i] - sorted_timestamps[i-1])
        
        return {
            'count': len(prompts),
            'total_words': sum(word_counts),
            'avg_words': sum(word_counts) / len(prompts) if prompts else 0,
            'max_words': max(word_counts) if word_counts else 0,
            'min_words': min(word_counts) if word_counts else 0,
            'total_chars': sum(char_counts),
            'avg_chars': sum(char_counts) / len(prompts) if prompts else 0,
            'timestamps': timestamps,
            'time_diffs': time_diffs
        }
    
    def categorize_prompt(self, prompt_text):
        """Categorize a prompt based on its content"""
        prompt_text = prompt_text.lower()
        
        categories = []
        
        # Check for code-related prompts
        code_indicators = ['function', 'class', 'implement', 'code', 'bug', 'fix', 'error', 
                          'python', 'javascript', 'html', 'css', 'syntax']
        if any(word in prompt_text for word in code_indicators):
            categories.append('code')
            
        # Check for explanation requests
        explain_indicators = ['explain', 'how does', 'what is', 'describe', 'tell me about']
        if any(phrase in prompt_text for phrase in explain_indicators):
            categories.append('explanation')
            
        # Check for debugging requests
        debug_indicators = ['debug', 'fix', 'error', 'issue', 'problem', 'not working']
        if any(word in prompt_text for word in debug_indicators):
            categories.append('debugging')
            
        # Check for feature development
        feature_indicators = ['feature', 'implement', 'add', 'create', 'develop']
        if any(word in prompt_text for word in feature_indicators):
            categories.append('feature')
            
        # Check for refactoring
        refactor_indicators = ['refactor', 'improve', 'optimize', 'clean', 'better']
        if any(word in prompt_text for word in refactor_indicators):
            categories.append('refactoring')
            
        # No categories identified - mark as general
        if not categories:
            categories.append('general')
            
        return categories
    
    def calculate_complexity_score(self, prompt_text):
        """Calculate a complexity score for a prompt
        
        Factors:
        - Length of prompt
        - Vocabulary diversity
        - Presence of technical terms
        - Question complexity (number of questions)
        """
        if not prompt_text or not isinstance(prompt_text, str):
            return 0
            
        # Base score based on length (0-10)
        length_score = min(10, len(prompt_text) / 100)
        
        # Vocabulary diversity (0-10)
        words = re.findall(r'\b\w+\b', prompt_text.lower())
        unique_words = set(words)
        vocab_diversity = len(unique_words) / len(words) if words else 0
        vocab_score = min(10, vocab_diversity * 10)
        
        # Technical terms (0-10)
        technical_terms = ['function', 'algorithm', 'implementation', 'architecture', 'design',
                         'interface', 'module', 'class', 'inheritance', 'polymorphism',
                         'database', 'query', 'optimization', 'complexity', 'asynchronous',
                         'concurrency', 'thread', 'process', 'memory', 'cache',
                         'framework', 'library', 'api', 'integration', 'deployment']
        tech_count = sum(1 for term in technical_terms if term in prompt_text.lower())
        tech_score = min(10, tech_count * 2)
        
        # Question complexity (0-10)
        question_count = prompt_text.count('?')
        question_score = min(10, question_count * 2)
        
        # Calculate total score (0-100)
        total_score = (length_score + vocab_score + tech_score + question_score) * 2.5
        return total_score
    
    def analyze_prompts(self):
        """Analyze all extracted prompts"""
        if not self.all_prompts:
            print("No prompts to analyze")
            return
            
        print(f"\nAnalyzing {len(self.all_prompts)} prompts across {len(self.workspaces)} workspaces")
        
        # Overall statistics
        stats = self.calculate_prompt_stats(self.all_prompts)
        
        # Calculate per-workspace statistics
        workspace_stats = {}
        for name, prompts in self.workspace_prompts.items():
            workspace_stats[name] = self.calculate_prompt_stats(prompts)
        
        # Categorize prompts
        categories = defaultdict(int)
        for prompt in self.all_prompts:
            prompt_text = prompt.get('text', '')
            prompt_categories = self.categorize_prompt(prompt_text)
            for category in prompt_categories:
                categories[category] += 1
                
        # Calculate complexity scores
        complexity_scores = []
        for prompt in self.all_prompts:
            prompt_text = prompt.get('text', '')
            score = self.calculate_complexity_score(prompt_text)
            complexity_scores.append(score)
        
        # Time analysis
        timestamps = []
        for prompt in self.all_prompts:
            if 'timestamp' in prompt:
                timestamps.append(prompt['timestamp'])
        
        # Generate report
        self.generate_report(stats, workspace_stats, categories, complexity_scores, timestamps)
        
        # Generate visualizations
        self.generate_visualizations(stats, workspace_stats, categories, complexity_scores, timestamps)
    
    def generate_report(self, stats, workspace_stats, categories, complexity_scores, timestamps):
        """Generate a detailed report of the analysis"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_dir, f"prompt_analysis_report_{timestamp}.md")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Cursor Prompt Analysis Report\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall statistics
            f.write("## Overall Statistics\n\n")
            f.write(f"- Total workspaces analyzed: {len(self.workspaces)}\n")
            f.write(f"- Total prompts: {stats['count']}\n")
            f.write(f"- Total words: {stats['total_words']}\n")
            f.write(f"- Average words per prompt: {stats['avg_words']:.1f}\n")
            f.write(f"- Longest prompt: {stats['max_words']} words\n")
            f.write(f"- Shortest prompt: {stats['min_words']} words\n")
            f.write(f"- Average characters per prompt: {stats['avg_chars']:.1f}\n")
            
            # Per-workspace statistics
            f.write("\n## Statistics by Workspace\n\n")
            f.write("| Workspace | Prompts | Total Words | Avg Words | Max Words |\n")
            f.write("|-----------|---------|-------------|-----------|----------|\n")
            
            for name, ws_stats in workspace_stats.items():
                f.write(f"| {name} | {ws_stats['count']} | {ws_stats['total_words']} | {ws_stats['avg_words']:.1f} | {ws_stats['max_words']} |\n")
            
            # Categories
            f.write("\n## Prompt Categories\n\n")
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(self.all_prompts)) * 100
                f.write(f"- {category}: {count} prompts ({percentage:.1f}%)\n")
                
            # Complexity
            if complexity_scores:
                avg_complexity = sum(complexity_scores) / len(complexity_scores)
                max_complexity = max(complexity_scores)
                min_complexity = min(complexity_scores)
                
                f.write("\n## Complexity Analysis\n\n")
                f.write(f"- Average complexity score: {avg_complexity:.1f}/100\n")
                f.write(f"- Highest complexity score: {max_complexity:.1f}/100\n")
                f.write(f"- Lowest complexity score: {min_complexity:.1f}/100\n")
                
            # Time analysis (if timestamps available)
            if timestamps:
                f.write("\n## Time Analysis\n\n")
                if len(timestamps) >= 2:
                    sorted_timestamps = sorted(timestamps)
                    first_prompt = datetime.fromtimestamp(sorted_timestamps[0]/1000)
                    last_prompt = datetime.fromtimestamp(sorted_timestamps[-1]/1000)
                    total_days = (last_prompt - first_prompt).days
                    
                    f.write(f"- First prompt: {first_prompt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"- Last prompt: {last_prompt.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"- Time span: {total_days} days\n")
                    
                    if total_days > 0:
                        prompts_per_day = len(timestamps) / total_days
                        f.write(f"- Average prompts per day: {prompts_per_day:.1f}\n")
        
        print(f"\nReport generated: {report_file}")
    
    def generate_visualizations(self, stats, workspace_stats, categories, complexity_scores, timestamps):
        """Generate visualizations for the analysis"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Create a subfolder for visualizations
            viz_dir = os.path.join(self.output_dir, "visualizations")
            if not os.path.exists(viz_dir):
                os.makedirs(viz_dir)
                
            # 1. Prompts per workspace
            if workspace_stats:
                plt.figure(figsize=(10, 6))
                names = list(workspace_stats.keys())
                counts = [ws_stats['count'] for ws_stats in workspace_stats.values()]
                
                plt.bar(names, counts)
                plt.title('Prompts per Workspace')
                plt.xlabel('Workspace')
                plt.ylabel('Number of Prompts')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"prompts_per_workspace_{timestamp}.png"))
                plt.close()
                
            # 2. Prompt categories
            if categories:
                plt.figure(figsize=(10, 6))
                names = list(categories.keys())
                counts = list(categories.values())
                
                plt.bar(names, counts)
                plt.title('Prompt Categories')
                plt.xlabel('Category')
                plt.ylabel('Number of Prompts')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"prompt_categories_{timestamp}.png"))
                plt.close()
                
            # 3. Complexity histogram
            if complexity_scores:
                plt.figure(figsize=(10, 6))
                plt.hist(complexity_scores, bins=20)
                plt.title('Prompt Complexity Distribution')
                plt.xlabel('Complexity Score')
                plt.ylabel('Number of Prompts')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"complexity_histogram_{timestamp}.png"))
                plt.close()
                
            # 4. Time series (if timestamps available)
            if timestamps and len(timestamps) >= 2:
                plt.figure(figsize=(12, 6))
                
                # Convert timestamps to datetime objects
                dates = [datetime.fromtimestamp(ts/1000) for ts in sorted(timestamps)]
                
                # Count prompts per day
                date_counts = Counter([date.date() for date in dates])
                
                # Sort by date
                sorted_dates = sorted(date_counts.keys())
                counts = [date_counts[date] for date in sorted_dates]
                
                plt.plot(sorted_dates, counts, marker='o')
                plt.title('Prompts Activity Over Time')
                plt.xlabel('Date')
                plt.ylabel('Number of Prompts')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"activity_timeline_{timestamp}.png"))
                plt.close()
                
            print(f"Visualizations saved to: {viz_dir}")
            
        except Exception as e:
            print(f"Error generating visualizations: {str(e)}")

def batch_process_workspaces(workspace_ids=None, copy_all=False):
    """Process multiple workspaces at once"""
    # Find all available workspaces
    workspaces = find_workspace_files()
    
    if not workspaces:
        print("No workspaces found.")
        return
        
    print(f"Found {len(workspaces)} workspaces")
    
    # Initialize the analyzer
    analyzer = WorkspaceAnalyzer()
    
    # Determine which workspaces to process
    workspaces_to_process = []
    
    if copy_all:
        # Process all workspaces
        workspaces_to_process = workspaces
    elif workspace_ids:
        # Process specified workspaces
        for id_str in workspace_ids:
            try:
                # Try to interpret as an index
                idx = int(id_str) - 1
                if 0 <= idx < len(workspaces):
                    workspaces_to_process.append(workspaces[idx])
                    continue
            except ValueError:
                pass
                
            # Try to interpret as a name
            for workspace in workspaces:
                if workspace['name'] and id_str.lower() in workspace['name'].lower():
                    workspaces_to_process.append(workspace)
                    break
    else:
        # Interactive selection
        print("Available workspaces:")
        for i, workspace in enumerate(workspaces):
            name = workspace['name'] or 'Unknown'
            has_db = "✓" if workspace['has_state_db'] else "✗"
            print(f"{i+1}. {name} [{has_db}]")
            
        selected_indices = input("\nEnter the numbers of workspaces to analyze (comma-separated, or 'all'): ")
        
        if selected_indices.lower() == 'all':
            workspaces_to_process = workspaces
        else:
            for idx_str in selected_indices.split(','):
                try:
                    idx = int(idx_str.strip()) - 1
                    if 0 <= idx < len(workspaces):
                        workspaces_to_process.append(workspaces[idx])
                except ValueError:
                    print(f"Invalid input: {idx_str}")
    
    # Process each selected workspace
    for workspace in workspaces_to_process:
        if not workspace['has_state_db']:
            print(f"Skipping workspace '{workspace['name']}' (no database file)")
            continue
            
        print(f"Processing workspace: {workspace['name']}")
        
        # Add the workspace to our analyzer
        analyzer.add_workspace(workspace, workspace['state_db_path'])
    
    # Process all the workspaces
    analyzer.process_all_workspaces()
    
    # Analyze the prompts
    analyzer.analyze_prompts()

def main():
    """Main function to run the batch workspace analyzer"""
    parser = argparse.ArgumentParser(description='Batch analyze Cursor workspaces')
    
    parser.add_argument('--all', '-a', action='store_true', 
                       help='Process all available workspaces')
    parser.add_argument('--workspaces', '-w', nargs='+', 
                       help='Specify workspaces to process (by name or number)')
    parser.add_argument('--output-dir', '-o', default='analysis_results',
                       help='Directory to save analysis results')
    
    args = parser.parse_args()
    
    batch_process_workspaces(args.workspaces, args.all)

if __name__ == "__main__":
    main() 