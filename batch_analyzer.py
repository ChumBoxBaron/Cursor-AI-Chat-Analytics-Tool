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
    
    def estimate_time_spent(self, prompts):
        """Estimate time spent based on prompt complexity and length
        
        This uses Method 1 (prompt-based estimation) to calculate time spent
        on AI interactions based on prompt characteristics.
        """
        if not prompts:
            return {
                'total_hours': 0,
                'avg_minutes_per_prompt': 0,
                'longest_prompt_minutes': 0
            }
        
        # Parameters - adjust these to calibrate the estimate
        avg_minutes_per_prompt = 5      # Base time per prompt
        complexity_factor = 0.5         # Additional minutes per complexity point (0-100 scale)
        words_per_minute_reading = 180  # Average reading speed (responses)
        words_per_minute_writing = 20   # Average writing speed (prompts)
        thinking_factor = 1.5           # Multiplier for thinking time
        
        total_minutes = 0
        prompt_times = []
        time_per_prompt = {}
        
        for i, prompt in enumerate(prompts):
            prompt_text = prompt.get('text', '')
            word_count = count_words(prompt_text)
            complexity = self.calculate_complexity_score(prompt_text)
            
            # Basic time (minimum time per prompt)
            prompt_minutes = avg_minutes_per_prompt
            
            # Add time based on writing the prompt
            writing_time = word_count / words_per_minute_writing
            
            # Add time based on complexity (thinking time)
            thinking_time = (complexity * complexity_factor / 10) * thinking_factor
            
            # Add time for reading the response (estimated)
            # Assuming response is about 2x the prompt length on average
            response_reading_time = (word_count * 2) / words_per_minute_reading
            
            # Total time for this prompt
            total_prompt_time = prompt_minutes + writing_time + thinking_time + response_reading_time
            prompt_times.append(total_prompt_time)
            
            # Store time components for later breakdown
            time_per_prompt[i] = {
                'total': total_prompt_time,
                'base': prompt_minutes,
                'writing': writing_time,
                'thinking': thinking_time,
                'reading': response_reading_time,
                'complexity': complexity,
                'word_count': word_count
            }
            
            total_minutes += total_prompt_time
        
        # Calculate some statistics
        total_hours = total_minutes / 60
        avg_minutes_per_prompt = total_minutes / len(prompts)
        longest_prompt_time = max(prompt_times)
        
        # Calculate productive days equivalent
        productive_hours_per_day = 4  # Assuming 4 productive hours per day
        days_equivalent = total_hours / productive_hours_per_day
        
        return {
            'total_hours': total_hours,
            'total_minutes': total_minutes,
            'avg_minutes_per_prompt': avg_minutes_per_prompt,
            'longest_prompt_minutes': longest_prompt_time,
            'days_equivalent': days_equivalent,
            'productive_hours_per_day': productive_hours_per_day,
            'time_per_prompt': time_per_prompt
        }
    
    def analyze_files_for_sessions(self, workspace_path):
        """Method 2: Analyze file changes to estimate working sessions
        
        This examines file timestamps to identify work sessions and
        calculate time spent based on file modifications.
        """
        if not workspace_path or not os.path.exists(workspace_path):
            return {
                'total_hours': 0,
                'sessions': 0,
                'avg_session_hours': 0,
                'session_details': []
            }
        
        # Look for code files
        file_times = []
        code_file_count = 0
        total_file_count = 0
        
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                # Skip hidden folders and files
                if any(part.startswith('.') for part in root.split(os.sep)) or file.startswith('.'):
                    continue
                    
                total_file_count += 1
                
                # Focus on code files
                if file.endswith(('.py', '.js', '.html', '.css', '.ts', '.jsx', '.tsx', '.md', '.json')):
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        ctime = os.path.getctime(filepath)
                        # Use creation time if it's earlier
                        file_time = min(mtime, ctime)
                        file_times.append((file_time, filepath))
                        code_file_count += 1
                    except Exception as e:
                        print(f"Error getting file time for {filepath}: {str(e)}")
        
        # If no files found, try to read any file timestamps
        if not file_times and total_file_count > 0:
            print("No code files found. Checking all files instead.")
            for root, dirs, files in os.walk(workspace_path):
                for file in files:
                    # Skip hidden folders and files
                    if any(part.startswith('.') for part in root.split(os.sep)) or file.startswith('.'):
                        continue
                        
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        ctime = os.path.getctime(filepath)
                        # Use creation time if it's earlier
                        file_time = min(mtime, ctime)
                        file_times.append((file_time, filepath))
                    except Exception as e:
                        pass  # Silently ignore errors for fallback files
        
        if not file_times:
            return {
                'total_hours': 0,
                'sessions': 0,
                'avg_session_hours': 0, 
                'session_details': []
            }
        
        # Sort by timestamp
        file_times.sort()
        
        # Identify sessions (changes within idle_timeout minutes)
        idle_timeout_minutes = 30
        idle_timeout_seconds = idle_timeout_minutes * 60
        
        sessions = []
        if file_times:
            current_session = [file_times[0]]
            
            for i in range(1, len(file_times)):
                time_gap = file_times[i][0] - file_times[i-1][0]
                
                if time_gap > idle_timeout_seconds:
                    sessions.append(current_session)
                    current_session = [file_times[i]]
                else:
                    current_session.append(file_times[i])
            
            sessions.append(current_session)
        
        # Calculate total time
        total_hours = 0
        session_durations = []
        session_details = []
        
        for i, session in enumerate(sessions):
            if len(session) > 1:
                start_time = session[0][0]
                end_time = session[-1][0]
                start_dt = datetime.fromtimestamp(start_time)
                end_dt = datetime.fromtimestamp(end_time)
                
                # Add buffer time
                buffer_minutes = 10
                buffered_start = start_time - (buffer_minutes * 60)
                buffered_end = end_time + (buffer_minutes * 60)
                
                # Calculate duration with buffer
                duration_seconds = buffered_end - buffered_start
                duration_hours = duration_seconds / 3600
                
                # Cap at 8 hours per session
                if duration_hours > 8:
                    duration_hours = 8
                
                total_hours += duration_hours
                session_durations.append(duration_hours)
                
                # Store session details
                session_details.append({
                    'session_number': i+1,
                    'start_time': start_dt.strftime('%Y-%m-%d %H:%M'),
                    'end_time': end_dt.strftime('%H:%M'),
                    'duration_hours': duration_hours,
                    'file_count': len(session)
                })
        
        avg_session_hours = sum(session_durations) / len(session_durations) if session_durations else 0
        
        return {
            'total_hours': total_hours,
            'sessions': len(session_details),
            'avg_session_hours': avg_session_hours,
            'session_details': session_details,
            'code_file_count': code_file_count,
            'total_file_count': total_file_count,
            'earliest_file': datetime.fromtimestamp(file_times[0][0]) if file_times else None,
            'latest_file': datetime.fromtimestamp(file_times[-1][0]) if file_times else None,
        }
    
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
        
        # Estimate time spent
        time_stats = self.estimate_time_spent(self.all_prompts)
        
        # Calculate workspace-specific time estimates
        workspace_time_stats = {}
        for name, prompts in self.workspace_prompts.items():
            workspace_time_stats[name] = self.estimate_time_spent(prompts)
        
        # Try to analyze workspace files for session-based time estimation
        workspace_session_stats = {}
        for workspace in self.workspaces:
            workspace_name = workspace['info']['name'] or "Unknown"
            workspace_folder = workspace['info'].get('folder')
            
            if workspace_folder and os.path.exists(workspace_folder):
                workspace_session_stats[workspace_name] = self.analyze_files_for_sessions(workspace_folder)
            elif workspace_name == "First Project":
                # Try to find First Project specifically
                potential_paths = [
                    "C:\\Users\\dhimm\\OneDrive\\Desktop\\First Project",
                    "C:\\Users\\dhimm\\AppData\\Roaming\\Cursor\\User\\workspaceStorage\\2831a6dc7bdb03d09bbeea5e8e3c8bab"
                ]
                
                for path in potential_paths:
                    if os.path.exists(path):
                        workspace_session_stats[workspace_name] = self.analyze_files_for_sessions(path)
                        break
        
        # Generate report
        self.generate_report(stats, workspace_stats, categories, complexity_scores, timestamps, 
                             time_stats, workspace_time_stats, workspace_session_stats)
        
        # Generate visualizations
        self.generate_visualizations(stats, workspace_stats, categories, complexity_scores, timestamps,
                                    time_stats, workspace_time_stats, workspace_session_stats)
    
    def generate_report(self, stats, workspace_stats, categories, complexity_scores, timestamps,
                        time_stats, workspace_time_stats, workspace_session_stats):
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
            
            # Time estimation statistics
            f.write("\n## Time Spent Estimation\n\n")
            f.write("### Prompt-Based Estimate\n\n")
            f.write(f"- Total estimated time: {time_stats['total_hours']:.1f} hours ({time_stats['total_minutes']:.1f} minutes)\n")
            f.write(f"- Average time per prompt: {time_stats['avg_minutes_per_prompt']:.1f} minutes\n")
            f.write(f"- Longest prompt time: {time_stats['longest_prompt_minutes']:.1f} minutes\n")
            f.write(f"- Equivalent to approximately {time_stats['days_equivalent']:.1f} days ")
            f.write(f"(assuming {time_stats['productive_hours_per_day']} productive hours per day)\n")
            
            # Session-based estimates (if available)
            if any(workspace_session_stats.values()):
                f.write("\n### Session-Based Estimate\n\n")
                
                # Combined stats from all workspaces
                total_session_hours = sum(stats['total_hours'] for stats in workspace_session_stats.values() if stats['total_hours'] > 0)
                total_sessions = sum(stats['sessions'] for stats in workspace_session_stats.values())
                
                if total_session_hours > 0:
                    f.write(f"- Total time across all workspaces: {total_session_hours:.1f} hours\n")
                    f.write(f"- Total work sessions: {total_sessions}\n")
                    
                    # Compare with prompt-based estimate
                    diff_hours = abs(time_stats['total_hours'] - total_session_hours)
                    diff_percent = (diff_hours / ((time_stats['total_hours'] + total_session_hours) / 2)) * 100 if (time_stats['total_hours'] + total_session_hours) > 0 else 0
                    
                    f.write(f"- Difference between methods: {diff_hours:.1f} hours ({diff_percent:.1f}%)\n")
                    f.write(f"- Average estimate: {(time_stats['total_hours'] + total_session_hours) / 2:.1f} hours\n")
            
            # Per-workspace statistics
            f.write("\n## Statistics by Workspace\n\n")
            f.write("| Workspace | Prompts | Total Words | Avg Words | Est. Hours |\n")
            f.write("|-----------|---------|-------------|-----------|------------|\n")
            
            for name, ws_stats in workspace_stats.items():
                time_stat = workspace_time_stats.get(name, {'total_hours': 0})
                f.write(f"| {name} | {ws_stats['count']} | {ws_stats['total_words']} | " +
                       f"{ws_stats['avg_words']:.1f} | {time_stat['total_hours']:.1f} |\n")
            
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
            
            # Session details (if available)
            if any(workspace_session_stats.values()):
                f.write("\n## Work Session Details\n\n")
                
                for workspace_name, session_stats in workspace_session_stats.items():
                    if session_stats['sessions'] > 0:
                        f.write(f"### {workspace_name}\n\n")
                        f.write(f"- Total sessions: {session_stats['sessions']}\n")
                        f.write(f"- Total hours: {session_stats['total_hours']:.1f}\n")
                        f.write(f"- Average session length: {session_stats['avg_session_hours']:.1f} hours\n")
                        
                        if session_stats.get('earliest_file') and session_stats.get('latest_file'):
                            f.write(f"- First file modified: {session_stats['earliest_file'].strftime('%Y-%m-%d %H:%M')}\n")
                            f.write(f"- Last file modified: {session_stats['latest_file'].strftime('%Y-%m-%d %H:%M')}\n")
                        
                        f.write("\n#### Session Timeline\n\n")
                        f.write("| Session | Date | Time | Duration | Files Modified |\n")
                        f.write("|---------|------|------|----------|----------------|\n")
                        
                        for session in session_stats['session_details']:
                            f.write(f"| {session['session_number']} | {session['start_time'].split()[0]} | " +
                                   f"{session['start_time'].split()[1]}-{session['end_time']} | " +
                                   f"{session['duration_hours']:.1f}h | {session['file_count']} |\n")
                        
                        f.write("\n")
        
        print(f"\nReport generated: {report_file}")
    
    def generate_visualizations(self, stats, workspace_stats, categories, complexity_scores, timestamps,
                               time_stats, workspace_time_stats, workspace_session_stats):
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
                
            # 5. Time spent per workspace
            if workspace_time_stats:
                plt.figure(figsize=(10, 6))
                names = list(workspace_time_stats.keys())
                hours = [stats['total_hours'] for stats in workspace_time_stats.values()]
                
                plt.bar(names, hours)
                plt.title('Estimated Time Spent per Workspace')
                plt.xlabel('Workspace')
                plt.ylabel('Hours')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"time_per_workspace_{timestamp}.png"))
                plt.close()
                
            # 6. Time spent breakdown (prompt-based)
            if time_stats.get('time_per_prompt'):
                # Calculate average time components
                avg_base = 0
                avg_writing = 0
                avg_thinking = 0
                avg_reading = 0
                
                for prompt_id, time_data in time_stats['time_per_prompt'].items():
                    avg_base += time_data['base']
                    avg_writing += time_data['writing']
                    avg_thinking += time_data['thinking']
                    avg_reading += time_data['reading']
                
                total_prompts = len(time_stats['time_per_prompt'])
                if total_prompts > 0:
                    avg_base /= total_prompts
                    avg_writing /= total_prompts
                    avg_thinking /= total_prompts
                    avg_reading /= total_prompts
                
                # Create pie chart of time components
                plt.figure(figsize=(10, 6))
                labels = ['Base Time', 'Writing', 'Thinking', 'Reading Responses']
                sizes = [avg_base, avg_writing, avg_thinking, avg_reading]
                
                plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                plt.axis('equal')
                plt.title('Time Allocation per Prompt')
                plt.tight_layout()
                plt.savefig(os.path.join(viz_dir, f"time_breakdown_{timestamp}.png"))
                plt.close()
                
            # 7. Session timeline visualization (if available)
            if any(workspace_session_stats.values()):
                # Get workspace with the most sessions
                max_sessions_workspace = max(
                    workspace_session_stats.items(),
                    key=lambda x: x[1]['sessions'] if x[1]['sessions'] > 0 else 0,
                    default=(None, {'sessions': 0})
                )
                
                if max_sessions_workspace[0] and max_sessions_workspace[1]['sessions'] > 0:
                    workspace_name = max_sessions_workspace[0]
                    session_stats = max_sessions_workspace[1]
                    
                    # Create session timeline chart
                    if session_stats['session_details']:
                        plt.figure(figsize=(12, 6))
                        
                        session_nums = [s['session_number'] for s in session_stats['session_details']]
                        durations = [s['duration_hours'] for s in session_stats['session_details']]
                        dates = [s['start_time'].split()[0] for s in session_stats['session_details']]
                        
                        # Create a color map based on dates
                        unique_dates = list(set(dates))
                        colors = plt.cm.viridis(np.linspace(0, 1, len(unique_dates)))
                        date_colors = {date: colors[i] for i, date in enumerate(unique_dates)}
                        bar_colors = [date_colors[date] for date in dates]
                        
                        plt.bar(session_nums, durations, color=bar_colors)
                        plt.title(f'Work Sessions: {workspace_name}')
                        plt.xlabel('Session Number')
                        plt.ylabel('Duration (hours)')
                        plt.xticks(session_nums)
                        
                        # Add a legend for dates
                        handles = [plt.Rectangle((0,0),1,1, color=date_colors[date]) for date in unique_dates]
                        plt.legend(handles, unique_dates, title="Dates")
                        
                        plt.tight_layout()
                        plt.savefig(os.path.join(viz_dir, f"session_timeline_{timestamp}.png"))
                        plt.close()
                
            # 8. Method comparison (if both methods available)
            if workspace_time_stats and any(workspace_session_stats.values()):
                # Collect workspaces with both metrics
                comparison_data = []
                
                for name in workspace_time_stats.keys():
                    if name in workspace_session_stats and workspace_session_stats[name]['total_hours'] > 0:
                        comparison_data.append({
                            'name': name,
                            'prompt_hours': workspace_time_stats[name]['total_hours'],
                            'session_hours': workspace_session_stats[name]['total_hours']
                        })
                
                if comparison_data:
                    plt.figure(figsize=(10, 6))
                    
                    names = [d['name'] for d in comparison_data]
                    prompt_hours = [d['prompt_hours'] for d in comparison_data]
                    session_hours = [d['session_hours'] for d in comparison_data]
                    
                    x = np.arange(len(names))
                    width = 0.35
                    
                    plt.bar(x - width/2, prompt_hours, width, label='Prompt-based')
                    plt.bar(x + width/2, session_hours, width, label='Session-based')
                    
                    plt.title('Time Estimation Methods Comparison')
                    plt.xlabel('Workspace')
                    plt.ylabel('Hours')
                    plt.xticks(x, names, rotation=45, ha='right')
                    plt.legend()
                    
                    plt.tight_layout()
                    plt.savefig(os.path.join(viz_dir, f"method_comparison_{timestamp}.png"))
                    plt.close()
                
            print(f"Visualizations saved to: {viz_dir}")
            
        except Exception as e:
            print(f"Error generating visualizations: {str(e)}")

def batch_process_workspaces(workspace_ids=None, copy_all=False, analyze_folders=False):
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
        
        # For session-based analysis, try to find the source folder if analyze_folders is enabled
        if analyze_folders and workspace['folder']:
            # Check if the folder exists
            if os.path.exists(workspace['folder']):
                print(f"  Found source folder: {workspace['folder']}")
            else:
                print(f"  Source folder not found: {workspace['folder']}")
                
                # For First Project, try common paths
                if workspace['name'] == "First Project":
                    potential_paths = [
                        "C:\\Users\\dhimm\\OneDrive\\Desktop\\First Project",
                        "C:\\Users\\dhimm\\AppData\\Roaming\\Cursor\\User\\workspaceStorage\\2831a6dc7bdb03d09bbeea5e8e3c8bab"
                    ]
                    
                    for path in potential_paths:
                        if os.path.exists(path):
                            workspace['folder'] = path
                            print(f"  Found alternate path: {path}")
                            break
        
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
    parser.add_argument('--analyze-folders', '-f', action='store_true',
                       help='Analyze source folders for session-based time tracking')
    
    args = parser.parse_args()
    
    batch_process_workspaces(args.workspaces, args.all, args.analyze_folders)

if __name__ == "__main__":
    main() 