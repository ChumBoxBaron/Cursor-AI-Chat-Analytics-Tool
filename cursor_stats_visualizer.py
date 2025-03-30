import os
import json
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import defaultdict

class CursorStatsVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Cursor Stats Visualizer")
        self.root.geometry("800x600")
        
        # Data storage
        self.data_dir = os.path.join(os.path.expanduser("~"), "cursor_tracker_data")
        self.projects = self.load_projects()
        
        # Setup UI
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
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left panel for controls
        control_frame = ttk.LabelFrame(main_frame, text="Controls")
        control_frame.pack(side="left", fill="y", padx=10, pady=10)
        
        # Project selection
        ttk.Label(control_frame, text="Select Project:").pack(padx=5, pady=5)
        self.project_var = tk.StringVar()
        self.project_dropdown = ttk.Combobox(control_frame, textvariable=self.project_var, width=20)
        self.project_dropdown['values'] = list(self.projects.keys())
        self.project_dropdown.pack(padx=5, pady=5)
        self.project_dropdown.bind("<<ComboboxSelected>>", self.update_charts)
        
        # Chart type selection
        ttk.Label(control_frame, text="Select Chart Type:").pack(padx=5, pady=5)
        self.chart_var = tk.StringVar(value="Time Distribution")
        charts = [
            "Time Distribution", 
            "Word Count per Prompt", 
            "Prompts per Day",
            "Session Duration"
        ]
        for chart in charts:
            ttk.Radiobutton(control_frame, text=chart, value=chart, 
                           variable=self.chart_var).pack(anchor="w", padx=5, pady=2)
        
        ttk.Button(control_frame, text="Generate Chart", 
                  command=self.update_charts).pack(padx=5, pady=20)
        
        # Right panel for charts
        self.chart_frame = ttk.LabelFrame(main_frame, text="Charts")
        self.chart_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # Initially display a message
        self.message_label = ttk.Label(self.chart_frame, 
                                      text="Select a project and chart type, then click 'Generate Chart'",
                                      font=("Arial", 12))
        self.message_label.pack(expand=True)
        
        # Figure for matplotlib
        self.figure = plt.Figure(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, self.chart_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
    
    def update_charts(self, event=None):
        project_name = self.project_var.get()
        chart_type = self.chart_var.get()
        
        if not project_name or project_name not in self.projects:
            messagebox.showerror("Error", "Please select a valid project")
            return
        
        # Clear previous chart
        if hasattr(self, 'message_label') and self.message_label.winfo_exists():
            self.message_label.pack_forget()
        
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        project_data = self.projects[project_name]
        
        # Generate chart based on selection
        if chart_type == "Time Distribution":
            self.create_time_distribution_chart(ax, project_data)
        elif chart_type == "Word Count per Prompt":
            self.create_word_count_chart(ax, project_data)
        elif chart_type == "Prompts per Day":
            self.create_prompts_per_day_chart(ax, project_data)
        elif chart_type == "Session Duration":
            self.create_session_duration_chart(ax, project_data)
        
        # Update the chart display
        if not hasattr(self, 'canvas_widget_packed') or not self.canvas_widget_packed:
            self.canvas_widget.pack(fill="both", expand=True)
            self.canvas_widget_packed = True
        
        self.canvas.draw()
    
    def create_time_distribution_chart(self, ax, project_data):
        total_time = project_data["total_time"]  # in seconds
        
        if total_time == 0:
            ax.text(0.5, 0.5, "No time data available", 
                    horizontalalignment='center', verticalalignment='center')
            return
        
        # Calculate hours per day
        days_data = defaultdict(float)
        
        for session in project_data.get("sessions", []):
            start_time = datetime.datetime.fromisoformat(session["start_time"])
            date_str = start_time.strftime("%Y-%m-%d")
            duration_hours = session["duration_seconds"] / 3600
            days_data[date_str] += duration_hours
        
        # Sort by date
        dates = sorted(days_data.keys())
        hours = [days_data[date] for date in dates]
        
        # Format dates for display
        display_dates = [datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d") for date in dates]
        
        ax.bar(display_dates, hours, color='skyblue')
        ax.set_xlabel('Date')
        ax.set_ylabel('Hours')
        ax.set_title(f'Time Spent per Day - {project_data.get("total_prompts", 0)} Prompts')
        
        # Rotate date labels if there are many
        if len(dates) > 5:
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        # Add total hours as text
        total_hours = total_time / 3600
        ax.text(0.5, 0.9, f"Total: {total_hours:.1f} hours", 
                horizontalalignment='center', transform=ax.transAxes)
    
    def create_word_count_chart(self, ax, project_data):
        prompts = project_data.get("prompts", [])
        
        if not prompts:
            ax.text(0.5, 0.5, "No prompt data available", 
                    horizontalalignment='center', verticalalignment='center')
            return
        
        # Extract word counts
        word_counts = [prompt["word_count"] for prompt in prompts]
        
        # Calculate statistics
        avg_words = sum(word_counts) / len(word_counts)
        max_words = max(word_counts) if word_counts else 0
        
        # Create histogram
        ax.hist(word_counts, bins=10, color='lightgreen', edgecolor='black')
        ax.axvline(avg_words, color='red', linestyle='dashed', linewidth=1, label=f'Avg: {avg_words:.1f}')
        
        ax.set_xlabel('Word Count')
        ax.set_ylabel('Number of Prompts')
        ax.set_title(f'Word Count Distribution - {len(prompts)} Prompts')
        ax.legend()
    
    def create_prompts_per_day_chart(self, ax, project_data):
        prompts = project_data.get("prompts", [])
        
        if not prompts:
            ax.text(0.5, 0.5, "No prompt data available", 
                    horizontalalignment='center', verticalalignment='center')
            return
        
        # Count prompts per day
        days_data = defaultdict(int)
        
        for prompt in prompts:
            timestamp = datetime.datetime.fromisoformat(prompt["timestamp"])
            date_str = timestamp.strftime("%Y-%m-%d")
            days_data[date_str] += 1
        
        # Sort by date
        dates = sorted(days_data.keys())
        counts = [days_data[date] for date in dates]
        
        # Format dates for display
        display_dates = [datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%m/%d") for date in dates]
        
        ax.plot(display_dates, counts, marker='o', linestyle='-', color='purple')
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Prompts')
        ax.set_title('Prompts per Day')
        
        # Rotate date labels if there are many
        if len(dates) > 5:
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    def create_session_duration_chart(self, ax, project_data):
        sessions = project_data.get("sessions", [])
        
        if not sessions:
            ax.text(0.5, 0.5, "No session data available", 
                    horizontalalignment='center', verticalalignment='center')
            return
        
        # Extract durations in minutes
        durations = [session["duration_seconds"] / 60 for session in sessions]
        
        # Sort sessions by start time
        sessions_sorted = sorted(sessions, key=lambda x: x["start_time"])
        dates = [datetime.datetime.fromisoformat(session["start_time"]).strftime("%m/%d") for session in sessions_sorted]
        durations_sorted = [session["duration_seconds"] / 60 for session in sessions_sorted]
        
        # Calculate average session duration
        avg_duration = sum(durations) / len(durations)
        
        ax.bar(range(len(durations_sorted)), durations_sorted, color='orange')
        ax.axhline(avg_duration, color='red', linestyle='dashed', linewidth=1, label=f'Avg: {avg_duration:.1f} min')
        
        ax.set_xlabel('Session Number')
        ax.set_ylabel('Duration (minutes)')
        ax.set_title(f'Session Durations - {len(sessions)} Sessions')
        ax.set_xticks(range(len(durations_sorted)))
        ax.set_xticklabels([f"{i+1}" for i in range(len(durations_sorted))])
        ax.legend()

if __name__ == "__main__":
    root = tk.Tk()
    app = CursorStatsVisualizer(root)
    root.mainloop() 