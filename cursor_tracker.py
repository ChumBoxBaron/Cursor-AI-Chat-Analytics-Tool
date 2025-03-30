import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import datetime
import re
from pathlib import Path

class CursorTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Cursor Chat Tracker")
        self.root.geometry("600x550")
        self.root.resizable(True, True)
        
        # Make window stay on top
        self.root.attributes("-topmost", True)
        
        # Add always on top toggle
        self.stay_on_top = tk.BooleanVar(value=True)
        
        # Data storage
        self.data_dir = os.path.join(os.path.expanduser("~"), "cursor_tracker_data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.projects = self.load_projects()
        self.current_project = None
        
        # Set up the UI
        self.setup_ui()
        
    def load_projects(self):
        try:
            projects_file = os.path.join(self.data_dir, "projects.json")
            if os.path.exists(projects_file):
                with open(projects_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading projects: {str(e)}")
            return {}
    
    def save_projects(self):
        try:
            projects_file = os.path.join(self.data_dir, "projects.json")
            with open(projects_file, 'w') as f:
                json.dump(self.projects, f, indent=2)
        except Exception as e:
            print(f"Error saving projects: {str(e)}")
    
    def setup_ui(self):
        # Project selection frame
        project_frame = ttk.LabelFrame(self.root, text="Project")
        project_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(project_frame, text="Select or create a project:").grid(row=0, column=0, padx=5, pady=5)
        
        self.project_var = tk.StringVar()
        self.project_dropdown = ttk.Combobox(project_frame, textvariable=self.project_var, width=30)
        self.project_dropdown['values'] = list(self.projects.keys())
        self.project_dropdown.grid(row=0, column=1, padx=5, pady=5)
        self.project_dropdown.bind("<<ComboboxSelected>>", self.select_project)
        
        ttk.Button(project_frame, text="New Project", command=self.new_project).grid(row=0, column=2, padx=5, pady=5)
        
        # Add stay on top toggle
        ttk.Checkbutton(project_frame, text="Stay on Top", variable=self.stay_on_top, 
                      command=self.toggle_stay_on_top).grid(row=0, column=3, padx=5, pady=5)
        
        # Session tracking frame
        self.session_frame = ttk.LabelFrame(self.root, text="Session Tracking")
        self.session_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Prompt tracking
        ttk.Label(self.session_frame, text="Your Prompt:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.prompt_text = tk.Text(self.session_frame, height=5, width=50, wrap="word")
        self.prompt_text.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        ttk.Button(self.session_frame, text="Log Prompt", command=self.log_prompt).grid(row=2, column=0, padx=5, pady=5)
        
        # Timing tracking
        ttk.Label(self.session_frame, text="Track Time:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        
        self.timer_frame = ttk.Frame(self.session_frame)
        self.timer_frame.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        self.timer_var = tk.StringVar(value="00:00:00")
        self.timer_label = ttk.Label(self.timer_frame, textvariable=self.timer_var, font=("Arial", 16))
        self.timer_label.pack(side="left", padx=10)
        
        self.timer_running = False
        self.start_time = None
        self.elapsed_time = datetime.timedelta(0)
        
        self.start_button = ttk.Button(self.timer_frame, text="Start", command=self.start_timer)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(self.timer_frame, text="Stop", command=self.stop_timer, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        # Stats display
        self.stats_frame = ttk.LabelFrame(self.root, text="Project Stats")
        self.stats_frame.pack(fill="x", padx=10, pady=10)
        
        self.stats_text = tk.Text(self.stats_frame, height=8, width=50, wrap="word", state="disabled")
        self.stats_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        ttk.Button(self.stats_frame, text="Refresh Stats", command=self.update_stats).pack(padx=5, pady=5)
        
        # Disable session tracking until project is selected
        for child in self.session_frame.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Entry, tk.Text, ttk.Combobox)):
                child.configure(state="disabled")
    
    def toggle_stay_on_top(self):
        """Toggle whether the window stays on top of other windows"""
        is_on_top = self.stay_on_top.get()
        self.root.attributes("-topmost", is_on_top)
    
    def new_project(self):
        project_name = tk.simpledialog.askstring("New Project", "Enter project name:")
        if not project_name:
            return
            
        if project_name in self.projects:
            messagebox.showerror("Error", "Project already exists!")
            return
            
        self.projects[project_name] = {
            "created_at": datetime.datetime.now().isoformat(),
            "prompts": [],
            "sessions": [],
            "total_time": 0,  # in seconds
            "total_prompts": 0,
            "total_word_count": 0
        }
        
        self.save_projects()
        self.project_dropdown['values'] = list(self.projects.keys())
        self.project_var.set(project_name)
        self.select_project()
    
    def select_project(self, event=None):
        project_name = self.project_var.get()
        if not project_name or project_name not in self.projects:
            return
            
        self.current_project = project_name
        
        # Enable session tracking
        for child in self.session_frame.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Entry, tk.Text, ttk.Combobox)):
                child.configure(state="normal")
            
        # Update stats
        self.update_stats()
    
    def log_prompt(self):
        if not self.current_project:
            messagebox.showerror("Error", "Select a project first!")
            return
            
        prompt_text = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt_text:
            messagebox.showerror("Error", "Prompt is empty!")
            return
            
        word_count = len(re.findall(r'\b\w+\b', prompt_text))
        
        prompt_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "text": prompt_text,
            "word_count": word_count
        }
        
        self.projects[self.current_project]["prompts"].append(prompt_data)
        self.projects[self.current_project]["total_prompts"] += 1
        self.projects[self.current_project]["total_word_count"] += word_count
        
        self.save_projects()
        self.prompt_text.delete("1.0", "end")
        self.update_stats()
        
        messagebox.showinfo("Success", "Prompt logged successfully!")
    
    def start_timer(self):
        self.timer_running = True
        self.start_time = datetime.datetime.now()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.update_timer()
    
    def stop_timer(self):
        if not self.current_project or not self.timer_running:
            return
            
        self.timer_running = False
        end_time = datetime.datetime.now()
        duration = end_time - self.start_time
        self.elapsed_time += duration
        
        # Log session
        session_data = {
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration.total_seconds()
        }
        
        self.projects[self.current_project]["sessions"].append(session_data)
        self.projects[self.current_project]["total_time"] += duration.total_seconds()
        
        self.save_projects()
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.update_stats()
    
    def update_timer(self):
        if not self.timer_running:
            return
            
        current_time = datetime.datetime.now()
        current_duration = current_time - self.start_time + self.elapsed_time
        
        # Format time as HH:MM:SS
        hours, remainder = divmod(current_duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        self.timer_var.set(time_str)
        self.root.after(1000, self.update_timer)
    
    def update_stats(self):
        if not self.current_project:
            return
            
        project_data = self.projects[self.current_project]
        
        total_time = project_data["total_time"]  # in seconds
        hours, remainder = divmod(total_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        total_prompts = project_data["total_prompts"]
        total_words = project_data["total_word_count"]
        average_words = total_words / total_prompts if total_prompts > 0 else 0
        
        stats = f"Project: {self.current_project}\n\n"
        stats += f"Total Time: {time_str}\n"
        stats += f"Number of Prompts: {total_prompts}\n"
        stats += f"Total Word Count: {total_words}\n"
        stats += f"Average Words per Prompt: {average_words:.1f}\n"
        stats += f"Number of Sessions: {len(project_data['sessions'])}\n"
        
        self.stats_text.configure(state="normal")
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", stats)
        self.stats_text.configure(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = CursorTracker(root)
    root.mainloop() 