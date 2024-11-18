import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import threading
from datetime import datetime
import queue
import asyncio
import sys

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Define activities dictionary
ACTIVITIES = [
    {
        "name": "Gather Training Data", 
        "path": os.path.join(SCRIPT_DIR, "unique_face_base_emotional/gather_data.py"),
        "description": "Source for training"
    },
    {
        "name": "Extract Embeddings", 
        "path": os.path.join(SCRIPT_DIR, "unique_face_base_emotional/Extract_embeddings.py"),
        "description": "Get properties of face"
    },
    {
        "name": "Train Model", 
        "path": os.path.join(SCRIPT_DIR, "unique_face_base_emotional/Train_model.py"),
        "description": "Quick training of script (generating model)"
    },    
    {
        "name": "Face Recognition",
        "path": os.path.join(SCRIPT_DIR, "unique_face_base_emotional/Face_Recognizer_Emotion.py"),
        "description": "Real time face & emotion"
    }
]

class ActivityLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Activity Launcher")
        
        # Configure main window
        self.root.geometry("1000x700")
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create and configure treeview
        self.tree = ttk.Treeview(self.main_frame, columns=("Name", "Description", "Path"), show="headings", height=6)
        self.tree.heading("Name", text="Activity Name")
        self.tree.heading("Description", text="Description")
        self.tree.heading("Path", text="Python Path")
        
        # Set column widths
        self.tree.column("Name", width=150)
        self.tree.column("Description", width=400)
        self.tree.column("Path", width=200)
        
        self.tree.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Add scrollbar for tree
        tree_scrollbar = ttk.Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=2, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        # Init the terminal window view
        self.terminal = scrolledtext.ScrolledText(self.main_frame, height=20, width=100, bg='black', fg='white')
        self.terminal.grid(row=1, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        self.terminal.tag_configure('success', foreground='green', font=('TkDefaultFont', 10, 'bold'))
        self.terminal.tag_configure('error', foreground='red', font=('TkDefaultFont', 10, 'bold'))
        self.terminal.tag_configure('info', foreground='cyan', font=('TkDefaultFont', 10, 'bold'))
        
        # Buttons frame
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        # Buttons
        ttk.Button(button_frame, text="Run Selected", command=self.run_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Terminal", command=self.clear_terminal).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exit", command=root.quit).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=1)
        
        # Queue for thread-safe terminal updates
        self.output_queue = queue.Queue()
        self.root.after(100, self.check_output_queue)
        
        # Load activities on startup
        self.load_activities()

        # Start event loop thread
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
            
    def load_activities(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for activity in ACTIVITIES:
            self.tree.insert("", tk.END, values=(activity["name"], activity["description"], activity["path"]))
    
    def clear_terminal(self):
        self.terminal.delete(1.0, tk.END)
            
    def check_output_queue(self):
        while True:
            try:
                text, tag = self.output_queue.get_nowait()
                self.terminal.insert(tk.END, text, tag)
                self.terminal.see(tk.END)
            except queue.Empty:
                break
        self.root.after(100, self.check_output_queue)

    async def run_process_async(self, path, activity_name):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_msg = f"\n[{timestamp}] ⚡ Starting {activity_name}...\n\n"
        self.output_queue.put((start_msg, 'info'))

        try:
            # Set a larger buffer size for subprocess pipes
            process = await asyncio.create_subprocess_exec(
                sys.executable, path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024*1024  # 1MB buffer size
            )

            async def read_stream(stream, tag=''):
                buffer = ''
                while True:
                    chunk = await stream.read(8192)  # Read in smaller chunks
                    if not chunk:
                        break
                    text = chunk.decode()
                    buffer += text
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            self.output_queue.put((line + '\n', tag))
                
                # Handle any remaining text
                if buffer.strip():
                    self.output_queue.put((buffer + '\n', tag))

            # Read both stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, 'error')
            )

            await process.wait()
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if process.returncode == 0:
                end_msg = f"\n[{timestamp}] ✅ {activity_name} completed successfully!\n"
                self.output_queue.put((end_msg, 'success'))
            else:
                end_msg = f"\n[{timestamp}] ❌ {activity_name} failed with return code {process.returncode}\n"
                self.output_queue.put((end_msg, 'error'))

        except Exception as e:
            error_msg = f"\n[{timestamp}] ❌ Error running {activity_name}: {str(e)}\n"
            self.output_queue.put((error_msg, 'error'))

    def run_process(self, path, activity_name):
        future = asyncio.run_coroutine_threadsafe(
            self.run_process_async(path, activity_name),
            self.loop
        )
        future.add_done_callback(lambda f: self.handle_process_complete(f, activity_name))

    def handle_process_complete(self, future, activity_name):
        try:
            future.result()
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"\n[{timestamp}] ❌ Error in {activity_name}: {str(e)}\n"
            self.output_queue.put((error_msg, 'error'))
            
    def run_selected(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an activity to run!")
            return
            
        values = self.tree.item(selected_item[0])['values']
        path = values[2]
        activity_name = values[0]
        
        self.run_process(path, activity_name)

if __name__ == "__main__":
    root = tk.Tk()
    app = ActivityLauncherApp(root)
    root.mainloop()
