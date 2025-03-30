# Cursor Chat Analytics Tools

This project contains tools to help track and analyze your interactions with Cursor AI. These tools will help you understand how much time you spend, how many prompts you write, and gather analytics about your coding journey.

## Overview

Cursor stores chat data in SQLite database files called `state.vscdb` within your workspaces. This project provides tools to:

1. Extract existing chat history from Cursor's database files
2. Manually track new AI interactions
3. Visualize and analyze your chat data

## Finding Your Chat History Files

Cursor stores chat history in SQLite database files. Here's how to find them:

1. Navigate to this location in File Explorer (Windows): 
   ```
   %APPDATA%\Cursor\User\workspaceStorage
   ```
   (You can paste this directly in the File Explorer address bar)

2. Inside this folder are several directories with long hash names (e.g., `2831a6dc7bdb03d09bbeea5e8e3c8bab`), each representing a workspace.

3. To identify which hash folder corresponds to your specific project:
   - Open each folder and look for a file called `workspace.json`
   - Open this file in a text editor
   - Look for the `"folder"` entry which will show the path to your workspace
   - For example: `"folder": "file:///c%3A/Users/dhimm/OneDrive/Desktop/First%20Project"`
   - The last part (`First%20Project`) indicates this is the folder for your "First Project" workspace

4. Once you've identified the correct workspace folder, look for a file called `state.vscdb` within it

5. Copy this file to your project directory to analyze it with the tools below.

## Tools Included

### 1. Workspace Finder (find_workspace.py)

A tool to automatically find and identify Cursor workspaces and copy their state.vscdb files:

**Usage:**
```
# List all workspaces (non-interactive)
python find_workspace.py --list

# Copy a specific workspace by number or name
python find_workspace.py --copy "First Project" 
python find_workspace.py --copy 2

# Interactive mode
python find_workspace.py
```

**Features:**
- Automatically scans for all Cursor workspaces
- Shows workspace names and paths in a clear list
- Identifies which workspaces have state.vscdb files
- Copies the state.vscdb file from selected workspace with a descriptive name

### 2. Chat Database Extraction (extract_prompts.py)

Extracts your prompt history from a Cursor database file:

**Usage:**
```
python extract_prompts.py --file [path_to_state_vscdb]
```

**Features:**
- Extracts all prompts from the specified state.vscdb file
- Calculates total prompt count and word count
- Generates both markdown and text files with your chat history

### 3. Database Analysis (dump_database.py)

Examines the structure of Cursor's database file:

**Usage:**
```
python dump_database.py
```

**Features:**
- Shows all tables and data structure
- Identifies keys containing chat data
- Helps diagnose file format issues

### 4. Cursor Tracker App (cursor_tracker.py)

This is a GUI application that lets you manually track your Cursor AI interactions:

**Usage:**
```
python cursor_tracker.py
```

**Features:**
- Create and manage multiple projects
- Log prompts and automatically count words
- Track time spent on each session
- View statistics including total time, prompt count, and word count

### 5. Stats Visualizer (cursor_stats_visualizer.py)

This tool visualizes your tracked data with interactive charts and graphs:

**Usage:**
```
python cursor_stats_visualizer.py
```

**Features:**
- Multiple chart types including:
  - Time distribution by day
  - Word count histograms
  - Prompts per day trends
  - Session duration analysis
- Interactive interface to switch between projects and chart types

**Requires matplotlib:**
```
pip install matplotlib
```

### 6. Batch Workspace Analyzer (batch_analyzer.py)

This comprehensive tool analyzes prompt data across multiple workspaces, providing detailed metrics and visualizations:

**Usage:**
```
# Process all workspaces
python batch_analyzer.py --all

# Process specific workspaces by name or number
python batch_analyzer.py --workspaces "First Project" "Prompt tracker"
python batch_analyzer.py --workspaces 1 3

# Interactive mode (default)
python batch_analyzer.py

# Specify output directory
python batch_analyzer.py --output-dir "my_analysis"
```

**Features:**
- Batch processing of multiple workspaces at once
- Cross-project analytics to compare different workspaces
- Advanced metrics calculation:
  - Prompt categorization (code, explanation, debugging, etc.)
  - Complexity scoring of prompts
  - Time spent analysis based on prompt timestamps
  - Response length analysis (when available)
- Comprehensive report generation in markdown format
- Visualizations including:
  - Prompts per workspace
  - Prompt categories distribution
  - Complexity score histogram
  - Activity timeline over days/weeks

**Requirements:**
```
pip install matplotlib numpy textblob
```

## Getting Started

1. Make sure you have Python installed on your system (Python 3.6 or newer)
2. For basic tracking, no additional libraries are needed
3. For visualization, install matplotlib: `pip install matplotlib`
4. Run the appropriate script based on your needs:
   - To extract existing chat history: `python extract_prompts.py`
   - To manually track new interactions: `python cursor_tracker.py`
   - To visualize data: `python cursor_stats_visualizer.py`

## Project Progress

We've successfully:

1. Created tools to locate and extract Cursor chat logs
2. Analyzed the database structure to find where history is stored
3. Extracted a full prompt history (107 prompts, 5,770 words)
4. Built systems for manual tracking and visualization of metrics
5. Incorporated "stay on top" functionality to keep the tracker visible

## Roadmap

Future improvements planned:

1. **Enhanced Data Visualization**
   - Create more advanced charts and graphs
   - Add timeline views of your AI interactions
   - Visualize trends in your prompt writing style over time

2. **Cross-Workspace Analytics**
   - Combine data from multiple workspace databases
   - Track total Cursor usage across all projects
   - Compare metrics between different projects

3. **Automated Tracking**
   - Develop a system to periodically scan for new chat data
   - Automatically update analytics without manual export

4. **Export Options**
   - Add CSV and JSON export formats
   - Create shareable reports of your AI interaction statistics

5. **Integration Improvements**
   - Create browser extensions for better tracking
   - Develop a centralized database for all your chat analytics
   - Explore direct API integration with Cursor if it becomes available

## Data Storage

Extracted data is saved in the following locations:
- Extracted prompts: `extracted_prompts/` directory
- Manual tracking data: `~/cursor_tracker_data` directory 