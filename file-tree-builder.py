import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import datetime
import subprocess
import threading
import customtkinter as ctk
import ctypes
from ctypes import wintypes
import traceback # Import traceback for detailed error logging
import json

# Drag & drop support (using windnd for Windows focus, similar to example)
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False
    print("Optional dependency 'windnd' not found. Drag and drop will not work on Windows.")
    print("Install using: pip install windnd")

# ======================================================================
# DPI Awareness & Window Centering (from example)
# ======================================================================
try:
    # Try modern DPI awareness setting (Windows 8.1+)
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_PER_MONITOR_DPI_AWARE
except AttributeError:
    try:
        # Fallback for older Windows versions
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass # Not on Windows or ctypes issue

def get_scaling_factor():
    """Returns the system DPI scaling factor (e.g. 1.0 for 100%, 1.5 for 150%)."""
    try:
        # For Windows 10 and up
        shcore = ctypes.windll.shcore
        # Assuming PROCESS_PER_MONITOR_DPI_AWARE was set
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        # Get DPI for the primary monitor (or monitor associated with point 0,0)
        monitor = ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(0, 0), 2) # MONITOR_DEFAULTTOPRIMARY
        shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) # MDT_EFFECTIVE_DPI
        return dpi_x.value / 96.0
    except Exception:
        try:
            # Fallback method (older Windows)
            hdc = ctypes.windll.user32.GetDC(0)
            LOGPIXELSX = 88 # Used to query DPI
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return dpi / 96.0
        except Exception:
            return 1.0 # Default if everything fails

# ======================================================================
# RESOURCE HANDLING (from example, adapted)
# ======================================================================
def resource_path(relative_path):
    """
    Returnează calea absolută către o resursă, indiferent
    că rulăm din sursă, dintr-un build --onedir sau --onefile.
    """
    # 1. Build onefile? atunci PyInstaller dezarhivează tot într‑un temp
    if getattr(sys, '_MEIPASS', None):
        base_path = sys._MEIPASS
    # 2. Build onedir? atunci helper-ele stau lângă executabil
    elif getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    # 3. Modul “dev”, sursă Python
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def load_json_list(fname):
    path = resource_path(os.path.join("helpers", fname))
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] Could not load {fname}: {e}")
        return []    
    


# se încarcă o singură dată la start
lang_map = load_json_list("lang_map.json")                      # deja aveai
ignore_items_list = load_json_list("ignore_items.json")
ignore_exts_list  = load_json_list("ignore_exts.json")

def get_outputs_folder_path():
    """
    Returns the absolute path for the outputs folder.
    - If running from a PyInstaller .exe: create 'outputs' in the same folder as the .exe.
    - If running from source: create 'outputs' in the same folder as the .py script.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller EXE: outputs goes into the same folder as the .exe
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "outputs")  # FileTreeBuilder/outputs
    else:
        # Running from source (.py): same behavior as before
        script_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(script_dir, "outputs")

# Global variable for storing the last output path.
last_output_path = None
# Global flag for stopping the generation thread
stop_requested = False
# Global reference to the app instance for safe_update
app = None

# ======================================================================
# Core Logic Functions (No changes needed here for "No Content" mode)
# ======================================================================

def build_tree(current_path, ignored_items, root_path, status_callback):
    """
    Recursively builds a dictionary representing the folder and file hierarchy.
    Checks stop_requested flag periodically.
    Adds ignored folders to the tree but doesn't recurse into them.
    """
    global stop_requested
    if stop_requested: return None

    tree = {}
    try:
        # Avoid logging every single directory scan unless debugging is needed
        # safe_update(status_callback, f"Scanning: {current_path.relative_to(root_path)}")

        items_sorted = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))

        for item in items_sorted:
            if stop_requested: return None

            try:
                relative_path_str = item.relative_to(root_path).as_posix()
            except ValueError:
                 # This can happen with symlinks pointing outside the root
                 safe_update(status_callback, f"Warning: Skipping item outside root? '{item}'")
                 continue

            item_name = item.name

            # --- Check if item itself should be ignored ---
            # Check name first (common case)
            is_ignored = item_name in ignored_items
            # If not ignored by name, check full relative path
            if not is_ignored and relative_path_str != '.': # Avoid checking '.' against ignored items
                 is_ignored = relative_path_str in ignored_items
            # If file, also check extension
            if not is_ignored and item.is_file():
                 is_ignored = item.suffix in ignored_items

            if item.is_dir():
                if is_ignored:
                    # Add ignored directory name to tree, but mark it as empty/ignored
                    tree[item_name] = {} # Represent as empty directory in output
                    continue # IMPORTANT: Skip recursion into this ignored directory
                else:
                    # Recursively build subtree
                    subtree = build_tree(item, ignored_items, root_path, status_callback)
                    if subtree is not None: # Propagate stop signal if needed (subtree is None)
                        # Only add non-empty subtrees unless it's explicitly empty ({})
                        if subtree or isinstance(subtree, dict):
                           tree[item_name] = subtree
                    else:
                        return None # Stop requested during subdirectory scan
            elif item.is_file():
                tree[item_name] = None

    except PermissionError:
        safe_update(status_callback, f"Permission denied: '{current_path}'")
    except FileNotFoundError:
         safe_update(status_callback, f"Directory not found during scan: '{current_path}'")
    except OSError as e:
         # Catch other OS errors like 'Too many levels of symbolic links'
         safe_update(status_callback, f"OS Error scanning '{current_path}': {e}")
    except Exception as e:
        safe_update(status_callback, f"Error scanning '{current_path}': {e}")
        traceback.print_exc() # Log full traceback for unexpected errors

    # Return the generated tree dictionary. It might be empty if all items were ignored or inaccessible.
    return tree

def traverse_files(root_path, ignored_items, status_callback):
    """
    Walks through the directory and collects relative file paths,
    respecting ignored items (folders, files, extensions).
    Checks stop_requested flag periodically.
    """
    global stop_requested
    file_paths = []
    safe_update(status_callback, "Starting file traversal...")
    processed_dirs = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True, onerror=lambda e: safe_update(status_callback, f"Error accessing during walk: {e}")):
            if stop_requested: return None # Stop traversal

            current_path_obj = Path(dirpath)
            try:
                current_rel_dir = current_path_obj.relative_to(root_path)
            except ValueError:
                 safe_update(status_callback, f"Warning: Skipping directory outside root? '{dirpath}'")
                 dirnames[:] = [] # Don't traverse further down this path
                 continue

            processed_dirs += 1
            if processed_dirs % 50 == 0: # Update status periodically for large trees
                 safe_update(status_callback, f"Collecting files in: {current_rel_dir}...")

            # Filter dirnames in-place based on ignored folders/paths
            original_dirnames = list(dirnames) # Copy for iteration
            dirnames[:] = [d for d in original_dirnames
                           if d not in ignored_items and
                           (current_rel_dir / d).as_posix() not in ignored_items]

            for filename in filenames:
                if stop_requested: return None # Check frequently

                file_path = current_path_obj / filename
                try:
                    relative_file_path_str = file_path.relative_to(root_path).as_posix()
                except ValueError:
                     safe_update(status_callback, f"Warning: Skipping file outside root? '{file_path}'")
                     continue

                file_suffix = file_path.suffix

                # Check against ignored files (name or relative path) and extensions
                if filename in ignored_items or \
                   relative_file_path_str in ignored_items or \
                   file_suffix in ignored_items:
                    continue

                file_paths.append(relative_file_path_str)
    except Exception as e:
        safe_update(status_callback, f"Error during file traversal: {e}")
        traceback.print_exc()
        return None # Indicate error

    safe_update(status_callback, f"Finished file traversal. Found {len(file_paths)} files.")
    return sorted(file_paths) if not stop_requested else None


def build_target_tree(current_path, target_folders, target_files, target_extensions, root_path, status_callback):
    """
    Recursively builds a hierarchy including only items that meet the target filters.
    Checks stop_requested flag periodically.
    """
    global stop_requested
    if stop_requested: return None

    tree = {}
    try:
        # safe_update(status_callback, f"Scanning target: {current_path.relative_to(root_path)}")
        items_sorted = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))

        for item in items_sorted:
            if stop_requested: return None

            try:
                relative_path = item.relative_to(root_path)
                relative_path_str = relative_path.as_posix()
            except ValueError:
                 safe_update(status_callback, f"Warning: Skipping target item outside root? '{item}'")
                 continue

            item_name = item.name

            if item.is_dir():
                # --- Directory Logic ---
                # Is the directory itself explicitly targeted?
                dir_is_targeted = item_name in target_folders or relative_path_str in target_folders

                # Should we descend into this directory?
                # Yes if:
                # 1. It's explicitly targeted OR
                # 2. No specific folders are targeted (meaning scan all folders) OR
                # 3. Specific files/extensions are targeted (meaning this dir *might* contain them)
                should_descend = dir_is_targeted or \
                                 not target_folders or \
                                 bool(target_files or target_extensions)

                if should_descend:
                    subtree = build_target_tree(item, target_folders, target_files, target_extensions, root_path, status_callback)
                    if subtree is None: return None # Stop signal propagated

                    # Include this directory in the output tree if:
                    # 1. It was explicitly targeted OR
                    # 2. It contains targeted items (subtree is not empty)
                    if dir_is_targeted or subtree:
                         tree[item_name] = subtree

            elif item.is_file():
                # --- File Logic ---
                file_matches_criteria = False
                # Match by extension? (Only if target extensions are specified)
                if target_extensions and item.suffix in target_extensions:
                    file_matches_criteria = True
                # Match by specific file name or relative path? (Only if target files are specified)
                # This overrides extension match if both are specified and file name matches.
                if target_files and (item_name in target_files or relative_path_str in target_files):
                    file_matches_criteria = True
                # If no specific file/extension targets are given, include all files encountered
                if not target_files and not target_extensions:
                    file_matches_criteria = True

                # Check if the file is within a required directory path (if target folders specified)
                in_required_path = False
                if not target_folders:
                    in_required_path = True # No specific folders required
                else:
                    # Check if any parent part matches a target folder name or path
                    current_parts = relative_path.parent.parts
                    parent_rel_path_str = relative_path.parent.as_posix()
                    if parent_rel_path_str == '.': parent_rel_path_str = "" # Handle root

                    if any(part in target_folders for part in current_parts) or \
                       (parent_rel_path_str and parent_rel_path_str in target_folders):
                        in_required_path = True
                    # Additionally, check if the *file's directory itself* is targeted (edge case for file in root of targeted dir)
                    if not in_required_path and parent_rel_path_str in target_folders:
                         in_required_path = True


                if file_matches_criteria and in_required_path:
                    tree[item_name] = None

    except PermissionError:
        safe_update(status_callback, f"Permission denied: '{current_path}'")
    except FileNotFoundError:
         safe_update(status_callback, f"Directory not found during target scan: '{current_path}'")
    except OSError as e:
         safe_update(status_callback, f"OS Error scanning target '{current_path}': {e}")
    except Exception as e:
        safe_update(status_callback, f"Error scanning target '{current_path}': {e}")
        traceback.print_exc()

    return tree


def traverse_target_files(root_path, target_folders, target_files, target_extensions, status_callback):
    """
    Walks through the directory and collects relative file paths that match the target filters.
    Checks stop_requested flag periodically.
    """
    global stop_requested
    file_paths = []
    safe_update(status_callback, "Starting target file traversal...")
    processed_dirs = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True, onerror=lambda e: safe_update(status_callback, f"Error accessing during target walk: {e}")):
            if stop_requested: return None

            current_path_obj = Path(dirpath)
            try:
                current_rel_dir = current_path_obj.relative_to(root_path)
                current_rel_dir_str = current_rel_dir.as_posix()
                if current_rel_dir_str == '.': current_rel_dir_str = "" # Handle root case for checks
            except ValueError:
                 safe_update(status_callback, f"Warning: Skipping target directory outside root? '{dirpath}'")
                 dirnames[:] = []
                 continue

            processed_dirs += 1
            if processed_dirs % 50 == 0:
                 safe_update(status_callback, f"Collecting target files in: {current_rel_dir}...")

            # --- Directory Filtering (Pruning os.walk) ---
            original_dirnames = list(dirnames)
            dirnames[:] = [] # Clear and rebuild based on whether to descend
            for d in original_dirnames:
                if stop_requested: return None
                dir_rel_path_str = (current_rel_dir / d).as_posix()

                # Should we descend into this directory 'd'?
                scan_all_folders = not target_folders
                dir_is_targeted = d in target_folders or dir_rel_path_str in target_folders
                is_under_target_folder = False
                if target_folders:
                     for target_f in target_folders:
                         if dir_rel_path_str == target_f or dir_rel_path_str.startswith(target_f + '/'):
                              is_under_target_folder = True
                              break
                potential_container = bool(target_files or target_extensions)

                if scan_all_folders or dir_is_targeted or is_under_target_folder or potential_container:
                     dirnames.append(d)


            # --- File Filtering (within the current dirpath) ---
            for filename in filenames:
                if stop_requested: return None

                file_path = current_path_obj / filename
                try:
                    relative_file_path = file_path.relative_to(root_path)
                    relative_file_path_str = relative_file_path.as_posix()
                except ValueError:
                     safe_update(status_callback, f"Warning: Skipping target file outside root? '{file_path}'")
                     continue

                file_suffix = file_path.suffix
                file_name = file_path.name

                # 1. Check if the file itself matches target files/extensions
                file_criteria_met = False
                if target_extensions and file_suffix in target_extensions:
                    file_criteria_met = True
                if target_files and (file_name in target_files or relative_file_path_str in target_files):
                    file_criteria_met = True
                if not target_files and not target_extensions: # If no specific file targets, match all
                     file_criteria_met = True

                # 2. Check if the file resides within a required directory path
                path_criteria_met = False
                if not target_folders: # If no specific folders targeted, path is always OK
                    path_criteria_met = True
                else:
                    current_parts = relative_file_path.parent.parts
                    parent_rel_path_str = relative_file_path.parent.as_posix()
                    if parent_rel_path_str == '.': parent_rel_path_str = "" # Handle root case

                    if (relative_file_path.parent.name in target_folders) or \
                       (parent_rel_path_str and parent_rel_path_str in target_folders):
                         path_criteria_met = True
                    elif any(part in target_folders for part in current_parts):
                         path_criteria_met = True


                if file_criteria_met and path_criteria_met:
                    file_paths.append(relative_file_path_str)

    except Exception as e:
        safe_update(status_callback, f"Error during target file traversal: {e}")
        traceback.print_exc()
        return None # Indicate error

    safe_update(status_callback, f"Finished target file traversal. Found {len(file_paths)} files.")
    return sorted(file_paths) if not stop_requested else None


def print_tree(tree, prefix="", tree_lines=None):
    """
    Generates a list of strings representing the folder tree.
    Handles potentially None or non-dict subtrees gracefully.
    """
    if tree_lines is None:
        tree_lines = []
    if not isinstance(tree, dict): # Handle cases where tree might be None
        return tree_lines

    items = list(tree.items())
    for index, (name, subtree) in enumerate(items):
        is_last = index == len(items) - 1
        connector = "└── " if is_last else "├── "
        line = prefix + connector + name
        tree_lines.append(line)

        # Only recurse if the subtree is a dictionary (representing a directory)
        if isinstance(subtree, dict):
            extension = "    " if is_last else "│   "
            print_tree(subtree, prefix + extension, tree_lines)

    return tree_lines

def write_hierarchy(output_file, tree_lines, status_callback):
    """ Writes the folder and file hierarchy to the output file. """
    safe_update(status_callback, "Writing hierarchy...")
    output_file.write("Hierarchy of folders and files:\n\n")
    if not tree_lines:
        output_file.write("(No items to display based on filters)\n")
    else:
        for line in tree_lines:
            output_file.write(line + "\n")
    output_file.write("\n")

def write_file_contents(output_file, root_path, file_paths, status_callback):
    """
    Writes the content of each file (within triple backticks) to the output file.
    Checks stop_requested flag periodically.
    Handles empty file_paths list gracefully.
    """
    global stop_requested
    if not file_paths:
        output_file.write("Contents of files:\n\n(No files selected or found to include content)\n\n")
        safe_update(status_callback, "Skipping file content writing (no files selected).")
        return True # Nothing to write, but not an error or stop

    safe_update(status_callback, "Writing file contents...")
    output_file.write("Contents of files:\n\n")
    total_files = len(file_paths)
    for i, file_rel_path in enumerate(file_paths):
        if stop_requested:
            safe_update(status_callback, "Operation stopped during file writing.")
            output_file.write("\n--- OPERATION STOPPED ---\n")
            return False # Indicate stop

        safe_update(status_callback, f"Writing content: {file_rel_path} ({i+1}/{total_files})")
        output_file.write(f"{file_rel_path}:\n")

        # Determine language hint for markdown code block
        ext = Path(file_rel_path).suffix.lower()
        lang_hint = lang_map.get(ext, '')  # lang_map e global, încărcat o singură dată

        output_file.write(f"```{lang_hint}\n")
        full_path = root_path / file_rel_path
        content = ""
        try:
            # Try reading with UTF-8 first, fallback to latin-1 for binary/other files
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read(1024 * 1024) # Read up to 1MB to prevent memory issues with huge files
                    if len(content) == 1024 * 1024:
                         content += "\n... (file content truncated due to size)"
            except UnicodeDecodeError:
                 try:
                     with open(full_path, 'r', encoding='latin-1') as f:
                         content = f.read(1024 * 1024) # Read up to 1MB
                         if len(content) == 1024 * 1024:
                              content += "\n... (file content truncated due to size)"
                         content += "\n... (Note: Read using latin-1 encoding)"
                 except Exception as e_latin1:
                     content = f"Error reading file (latin-1 fallback failed): {e_latin1}"
            except Exception as e_read: # Catch other file reading errors like permission denied
                 content = f"Error reading file: {e_read}"

        except FileNotFoundError:
             content = f"Error: File not found at path '{full_path}' (maybe moved/deleted during scan?)"
        except Exception as e:
            content = f"Error accessing file: {e}"
            traceback.print_exc()

        output_file.write(content if content else "(empty file)")
        output_file.write("\n```\n\n")

    return True # Indicate success

# ============================================================================
# WORKER THREAD & UI SAFETY HELPERS (from example)
# ============================================================================
def safe_update(callback, *args):
    """ Safely schedule a GUI update from a background thread. """
    global app # Use the global app reference
    if app: # Ensure app exists and hasn't been destroyed
        try:
            # Check if the widget associated with the callback still exists
            # This is a basic check; specific widgets might need more care
            # Note: This check might not work reliably for all callback types.
            # It's primarily useful for direct widget updates.
            # if len(args) > 0 and isinstance(args[0], tk.Widget) and not args[0].winfo_exists():
            #      # print(f"Skipping update for potentially destroyed widget: {args[0]}")
            #      return
            app.after(0, callback, *args)
        except Exception as e:
            # Avoid crashing if the app is closing during an update
            # print(f"Safe update failed: {e}") # Uncomment for debugging if needed
            pass

# ======================================================================
# GUI Application Class (using CustomTkinter)
# ======================================================================
class FileTreeBuilderApp(ctk.CTk):
    def __init__(self):
        global app # Assign to the global reference
        super().__init__()
        app = self # Make this instance globally accessible for safe_update

        self.title("File Tree Builder")
        self.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close

        # --- Window Size and Centering ---
        window_width, window_height = 600, 450
        min_width, min_height = 600, 450
        try:
            scale = get_scaling_factor()
        except Exception:
            scale = 1.0
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        adjusted_width = int(window_width * scale)
        adjusted_height = int(window_height * scale)
        x = int((screen_width / 2) - (adjusted_width / 2))
        y = int((screen_height / 2) - (adjusted_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(min_width, min_height)

        # --- Main Frame ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(padx=15, pady=15, fill="both", expand=True)

        # Configure grid weights for responsiveness
        self.main_frame.grid_columnconfigure(1, weight=1) # Allow entry fields to expand
        self.main_frame.grid_rowconfigure(6, weight=1) # Status box row index

        # --- CREATE STATUS WIDGETS EARLY ---
        self.status_label = ctk.CTkLabel(self.main_frame, text="Status / Log:")
        self.status_text = ctk.CTkTextbox(self.main_frame, height=100, state="disabled", wrap="word", activate_scrollbars=False)

        # --- 1. Folder Path + Browse (with drag-and-drop) ---
        self.folder_label = ctk.CTkLabel(self.main_frame, text="Folder Path:")
        self.folder_label.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="e")

        self.folder_path_var = tk.StringVar()
        self.folder_entry = ctk.CTkEntry(self.main_frame,
                                        textvariable=self.folder_path_var,
                                        width=350)

        # ── NEW: give it Undo / Redo ──────────────────────────────────────────
        self._enable_undo_redo(self.folder_entry)
        self.folder_entry.grid(row=0, column=1, padx=0, pady=10, sticky="ew")

        self.browse_button = ctk.CTkButton(self.main_frame, text="Browse", width=80, command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, padx=(10, 0), pady=10)

        if HAS_WINDND:
            windnd.hook_dropfiles(self, func=self.on_folder_drop)
            self.folder_entry.configure(placeholder_text="Enter path or drag & drop folder here")
        else:
            self.folder_entry.configure(placeholder_text="Enter path")

        # --- 2. Mode Selection ---
        self.mode_label = ctk.CTkLabel(self.main_frame, text="Mode:")
        self.mode_label.grid(row=1, column=0, padx=(0, 10), pady=10, sticky="e")

        self.mode_var = tk.StringVar(value="Classic")
        # Add "No Content" to the dropdown values
        self.mode_dropdown = ctk.CTkOptionMenu(self.main_frame, variable=self.mode_var,
                                               values=["Classic", "Target", "No Content"],
                                               command=self.update_mode_ui)
        self.mode_dropdown.grid(row=1, column=1, padx=0, pady=10, sticky="w")

        # --- 3. Classic / No Content mode fields (Ignore) ---
        self.ignore_label = ctk.CTkLabel(self.main_frame, text="Ignore Items:")
        self.ignore_ext_label = ctk.CTkLabel(self.main_frame, text="Ignore Exts:")

        # la iniţializare:
        default_ignore_items = "|".join(ignore_items_list)
        default_ignore_exts  = "|".join(ignore_exts_list)

        self.ignore_var = tk.StringVar(value=default_ignore_items)
        self.ignore_entry = ctk.CTkEntry(self.main_frame, textvariable=self.ignore_var, width=350,
                                         placeholder_text="e.g. .git|node_modules|temp.log")
        self._enable_undo_redo(self.ignore_entry)

        self.ignore_ext_var = tk.StringVar(value=default_ignore_exts)
        self.ignore_ext_entry = ctk.CTkEntry(self.main_frame, textvariable=self.ignore_ext_var, width=350,
                                             placeholder_text="e.g. log|tmp|.bak (no dot needed)")
        self._enable_undo_redo(self.ignore_ext_entry)

        # --- 4. Target mode fields ---
        self.target_label = ctk.CTkLabel(self.main_frame, text="Target Items:")
        self.target_ext_label = ctk.CTkLabel(self.main_frame, text="Target Exts:")


        self.target_var = tk.StringVar()
        self.target_entry = ctk.CTkEntry(self.main_frame, textvariable=self.target_var, width=350,
                                         placeholder_text="e.g. src|docs/readme.md|main.py")
        self._enable_undo_redo(self.target_entry)

        self.target_ext_var = tk.StringVar()
        self.target_ext_entry = ctk.CTkEntry(self.main_frame, textvariable=self.target_ext_var, width=350,
                                             placeholder_text="e.g. py|md|cpp (no dot needed)")
        self._enable_undo_redo(self.target_ext_entry)

        # Place filter fields in grid (Rows 2 & 3)
        self.ignore_label.grid(row=2, column=0, padx=(0, 10), pady=5, sticky="e")
        self.ignore_entry.grid(row=2, column=1, columnspan=2, padx=0, pady=5, sticky="ew")
        self.ignore_ext_label.grid(row=3, column=0, padx=(0, 10), pady=5, sticky="e")
        self.ignore_ext_entry.grid(row=3, column=1, columnspan=2, padx=0, pady=5, sticky="ew")

        self.target_label.grid(row=2, column=0, padx=(0, 10), pady=5, sticky="e")
        self.target_entry.grid(row=2, column=1, columnspan=2, padx=0, pady=5, sticky="ew")
        self.target_ext_label.grid(row=3, column=0, padx=(0, 10), pady=5, sticky="e")
        self.target_ext_entry.grid(row=3, column=1, columnspan=2, padx=0, pady=5, sticky="ew")

        # --- NOW it's safe to call update_mode_ui ---
        self.update_mode_ui(self.mode_var.get()) # Set initial visibility

        # --- 5. Buttons: Run / Stop / Open Output ---
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=4, column=0, columnspan=3, pady=(15, 10))
        self.button_frame.grid_columnconfigure((0, 1, 2), weight=1) # Center buttons

        self.run_button = ctk.CTkButton(self.button_frame, text="Run Generation", command=self.start_generation)
        self.run_button.grid(row=0, column=0, padx=10)

        self.stop_button = ctk.CTkButton(self.button_frame, text="Stop", command=self.on_stop, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=10)

        self.open_output_button = ctk.CTkButton(self.button_frame, text="Open Output Folder", command=self.open_output, state="disabled")
        self.open_output_button.grid(row=0, column=2, padx=10)

        # --- 6. GRID the Status Textbox (created earlier) ---
        self.status_label.grid(row=5, column=0, padx=(0, 10), pady=(10, 0), sticky="nw")
        self.status_text.grid(row=6, column=0, columnspan=3, padx=0, pady=(0,10), sticky="nsew")
        self.update_status("Ready. Select a folder and click 'Run Generation'.")

        # --- Initialize ---
        self.generation_thread = None
        # Schedule the initial status update slightly delayed
        # self.after(50, lambda: self.update_status("Ready. Select a folder and click 'Run Generation'."))

    # ------------------------------------------------------------------
    #  Enable built‑in Tk undo/redo on a CustomTkinter Entry
    # ------------------------------------------------------------------
    def _enable_undo_redo(self, ctk_entry):
        """Enable Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z undo/redo on a CTkEntry."""
        # 1. Get the real tk.Entry inside CTkEntry:
        internal = getattr(ctk_entry, "_entry", None) or getattr(ctk_entry, "entry", ctk_entry)
        try:
            # 2. Try the built‑in undo (works only for Text)
            internal.configure(undo=True, autoseparators=True, maxundo=-1)
            internal.bind("<Control-z>",      lambda e: internal.edit_undo())
            internal.bind("<Control-y>",      lambda e: internal.edit_redo())
            internal.bind("<Control-Shift-Z>",lambda e: internal.edit_redo())
        except tk.TclError:
            # 3. Entry has no undo: set up manual history
            internal._undo_stack = [internal.get()]
            internal._undo_index = 0

            def _record_change(event=None):
                val = internal.get()
                # Push new state if it differs
                if val != internal._undo_stack[internal._undo_index]:
                    internal._undo_stack = internal._undo_stack[:internal._undo_index+1]
                    internal._undo_stack.append(val)
                    internal._undo_index += 1

            def _manual_undo(event=None):
                if internal._undo_index > 0:
                    internal._undo_index -= 1
                    internal.delete(0, tk.END)
                    internal.insert(0, internal._undo_stack[internal._undo_index])
                return "break"  # prevent default behavior

            def _manual_redo(event=None):
                if internal._undo_index < len(internal._undo_stack) - 1:
                    internal._undo_index += 1
                    internal.delete(0, tk.END)
                    internal.insert(0, internal._undo_stack[internal._undo_index])
                return "break"

            # 4. Bind recording and undo/redo keys
            internal.bind("<KeyRelease>",           _record_change)
            internal.bind("<Control-z>",            _manual_undo)
            internal.bind("<Control-y>",            _manual_redo)
            internal.bind("<Control-Shift-Z>",      _manual_redo)

    def update_status(self, message):
        """ Updates the status textbox safely. """
        # (No changes needed in this method)
        self.status_text.configure(state='normal')
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            last_msg = self.status_text.get("end-2l", "end-1l").strip()
            if message in last_msg:
                 self.status_text.configure(state='disabled')
                 return
        except tk.TclError:
            pass
        except Exception:
             pass

        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.configure(state='disabled')
        self.status_text.see(tk.END)

    def browse_folder(self):
        # (No changes needed in this method)
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_var.set(folder_selected)
            self.update_status(f"Folder selected: {folder_selected}")

    def on_folder_drop(self, files):
        # (No changes needed in this method)
        try:
            if files:
                folder_path = files[0].decode('utf-8')
                if os.path.isdir(folder_path):
                    self.folder_path_var.set(folder_path)
                    self.update_status(f"Folder dropped: {folder_path}")
                else:
                    self.update_status(f"Dropped item is not a folder: {folder_path}")
                    safe_update(messagebox.showwarning, "Invalid Drop", "Please drop a folder, not a file.")
        except Exception as e:
            self.update_status(f"Error processing dropped item: {e}")
            safe_update(messagebox.showerror, "Drop Error", f"Could not process dropped item:\n{e}")

    def update_mode_ui(self, mode):
        """ Show/hide the appropriate filter fields based on mode. """
        # Show Ignore fields for Classic and No Content, hide for Target
        if mode == "Classic" or mode == "No Content":
            self.ignore_label.grid()
            self.ignore_entry.grid()
            self.ignore_ext_label.grid()
            self.ignore_ext_entry.grid()
            self.target_label.grid_remove()
            self.target_entry.grid_remove()
            self.target_ext_label.grid_remove()
            self.target_ext_entry.grid_remove()
        elif mode == "Target":
            self.ignore_label.grid_remove()
            self.ignore_entry.grid_remove()
            self.ignore_ext_label.grid_remove()
            self.ignore_ext_entry.grid_remove()
            self.target_label.grid()
            self.target_entry.grid()
            self.target_ext_label.grid()
            self.target_ext_entry.grid()
        # Always update status
        self.update_status(f"Mode switched to: {mode}")

    def _parse_filters(self, filter_string):
        # (No changes needed in this method)
        if not filter_string:
            return set()
        filters = set()
        for item in filter_string.split('|'):
            item = item.strip()
            if not item:
                 continue
            if item.startswith('*.'):
                 ext = '.' + item[2:]
                 filters.add(ext)
            else:
                 filters.add(item)
        return filters

    def _parse_extensions(self, ext_string):
        # (No changes needed in this method)
        extensions = set()
        if not ext_string:
            return extensions
        for ext in ext_string.split('|'):
            ext = ext.strip().lower()
            if ext:
                if not ext.startswith('.'):
                    ext = '.' + ext
                extensions.add(ext)
        return extensions

    def start_generation(self):
        """ Starts the generation process in a separate thread. """
        global stop_requested, last_output_path
        stop_requested = False
        last_output_path = None

        # --- Get and Validate Inputs ---
        folder_path_str = self.folder_path_var.get().strip()
        if not folder_path_str:
            safe_update(messagebox.showerror, "Error", "Please select a folder path.")
            self.update_status("Error: Folder path is required.")
            return

        root_path = Path(folder_path_str).resolve()
        if not root_path.is_dir():
            safe_update(messagebox.showerror, "Error", f"The path '{root_path}' is not a valid directory.")
            self.update_status(f"Error: Invalid directory '{root_path}'.")
            return

        mode = self.mode_var.get()

        # --- Parse Filters (Main Thread) ---
        all_ignored = set()
        target_folders = set()
        target_files = set()
        target_extensions = set()

        try:
            # Parse ignore filters for Classic and No Content modes
            if mode == "Classic" or mode == "No Content":
                ignore_items_str = self.ignore_var.get()
                ignore_ext_str = self.ignore_ext_var.get()
                ignored_items = self._parse_filters(ignore_items_str)
                ignored_extensions = self._parse_extensions(ignore_ext_str)
                all_ignored = ignored_items.union(ignored_extensions)
                if mode == "Classic":
                    self.update_status(f"Classic Mode: Ignoring {len(all_ignored)} patterns.")
                else: # No Content mode
                    self.update_status(f"No Content Mode: Applying {len(all_ignored)} ignore patterns to hierarchy.")

            # Parse target filters for Target mode
            elif mode == "Target":
                target_items_str = self.target_var.get()
                target_ext_str = self.target_ext_var.get()
                target_folders_files = self._parse_filters(target_items_str)
                target_extensions = self._parse_extensions(target_ext_str)
                target_folders = set(item for item in target_folders_files if '/' not in item and '.' not in item and item)
                target_files = target_folders_files - target_folders
                self.update_status(f"Target Mode: Targeting {len(target_folders)} folders, {len(target_files)} files, {len(target_extensions)} extensions.")

        except Exception as e:
             self.update_status(f"Error parsing filters: {e}")
             messagebox.showerror("Filter Error", f"Could not parse filters:\n{e}")
             return

        # --- Disable UI elements ---
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.open_output_button.configure(state="disabled")
        self.folder_entry.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.mode_dropdown.configure(state="disabled")
        # Disable relevant filter fields based on mode
        if mode == "Classic" or mode == "No Content":
            self.ignore_entry.configure(state="disabled")
            self.ignore_ext_entry.configure(state="disabled")
        elif mode == "Target":
            self.target_entry.configure(state="disabled")
            self.target_ext_entry.configure(state="disabled")

        self.update_status(f"Starting generation for '{root_path.name}' in {mode} mode...")

        # --- Prepare arguments for the thread ---
        thread_args = (root_path, mode, all_ignored, target_folders, target_files, target_extensions)

        # --- Start the background thread ---
        self.generation_thread = threading.Thread(target=self._run_generation_thread, args=thread_args, daemon=True)
        self.generation_thread.start()

    def _run_generation_thread(self, root_path, mode, all_ignored, target_folders, target_files, target_extensions):
        """ The actual workhorse function running in the background thread. """
        global stop_requested, last_output_path
        try:
            tree = None
            # file_paths list is only needed for modes that include content
            file_paths = None # Initialize as None

            # --- Build Tree Structure ---
            if mode == "Classic" or mode == "No Content":
                safe_update(self.update_status, "Building tree structure...")
                tree = build_tree(root_path, all_ignored, root_path, self.update_status)
                if stop_requested: raise InterruptedError("Operation stopped by user.")
                if tree is None and not stop_requested:
                    safe_update(self.update_status, "Warning: Could not build tree structure (check permissions?).")
                    tree = {} # Default to empty tree on error

            elif mode == "Target":
                safe_update(self.update_status, "Building target tree structure...")
                tree = build_target_tree(root_path, target_folders, target_files, target_extensions, root_path, self.update_status)
                if stop_requested: raise InterruptedError("Operation stopped by user.")
                if tree is None and not stop_requested:
                    safe_update(self.update_status, "Warning: Could not build target tree structure.")
                    tree = {}

            # --- Traverse Files (Only if content is needed) ---
            if mode == "Classic":
                safe_update(self.update_status, "Traversing files for content...")
                file_paths = traverse_files(root_path, all_ignored, self.update_status)
                if stop_requested: raise InterruptedError("Operation stopped by user.")
                if file_paths is None and not stop_requested:
                     safe_update(self.update_status, "Warning: Could not traverse files (check permissions?).")
                     file_paths = [] # Default to empty list on error

            elif mode == "Target":
                safe_update(self.update_status, "Traversing target files for content...")
                file_paths = traverse_target_files(root_path, target_folders, target_files, target_extensions, self.update_status)
                if stop_requested: raise InterruptedError("Operation stopped by user.")
                if file_paths is None and not stop_requested:
                    safe_update(self.update_status, "Warning: Could not traverse target files.")
                    file_paths = []

            # For "No Content" mode, file_paths remains None or becomes [] implicitly

            # Handle cases where nothing was found
            if not tree and (file_paths is None or not file_paths) and not stop_requested: # Adjusted check
                 safe_update(self.update_status, "Warning: No matching files or folders found based on filters.")
                 tree = tree if tree is not None else {}
                 file_paths = file_paths if file_paths is not None else [] # Ensure it's a list for write_file_contents

            # --- Generate Output File ---
            output_dir = Path(get_outputs_folder_path())
            output_dir.mkdir(exist_ok=True)

            folder_name = root_path.name if root_path.name else "root"
            # Add mode to filename for clarity, especially for No Content
            base_filename = f"{folder_name}_hierarchy_{mode.lower().replace(' ', '')}.txt"
            output_file_path = output_dir / base_filename

            counter = 1
            while output_file_path.exists():
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                new_filename = f"{folder_name}_hierarchy_{mode.lower().replace(' ', '')}_{now_str}.txt"
                output_file_path = output_dir / new_filename
                counter += 1
                if counter > 20:
                    safe_update(self.update_status, "Error: Could not create unique output filename after multiple attempts.")
                    raise IOError("Could not find a unique filename.")

            safe_update(self.update_status, f"Writing output to: {output_file_path}")

            with open(output_file_path, 'w', encoding='utf-8') as output_file:
                # Option 2: show root folder name first
                tree_lines = [root_path.name]
                tree_lines += print_tree(tree)
                write_hierarchy(output_file, tree_lines, self.update_status)
                if stop_requested: raise InterruptedError("Operation stopped by user.")

                # --- Write Content Section (Only if mode is NOT "No Content") ---
                if mode != "No Content":
                    # Ensure file_paths is a list before passing
                    current_file_paths = file_paths if file_paths is not None else []
                    write_ok = write_file_contents(output_file, root_path, current_file_paths, self.update_status)
                    if not write_ok:
                         raise InterruptedError("Operation stopped by user.")
                else:
                    # Optionally write a note that content was skipped
                    output_file.write("File contents skipped in 'No Content' mode.\n")
                    safe_update(self.update_status, "Skipping file content writing ('No Content' mode).")


            last_output_path = output_file_path
            success_msg = f"✅ Generation complete! Output saved to:\n{output_file_path}"
            safe_update(self.update_status, success_msg)
            safe_update(self.ask_open_output_folder, output_dir)

        except InterruptedError:
            safe_update(self.update_status, "🛑 Operation stopped by user.")
            if 'output_file_path' in locals() and output_file_path.exists():
                try:
                    with open(output_file_path, 'a', encoding='utf-8') as f:
                        f.write("\n\n--- GENERATION INTERRUPTED ---\n")
                    safe_update(self.update_status, f"Marked incomplete file: {output_file_path}")
                except Exception as e_write:
                    safe_update(self.update_status, f"Could not mark incomplete file: {e_write}")

        except Exception as e:
            error_msg = f"❌ An error occurred during generation: {e}"
            traceback.print_exc()
            safe_update(self.update_status, error_msg + " (See console for details)")
            safe_update(messagebox.showerror, "Error", f"An error occurred during generation:\n{e}\n\n(Check console for full traceback)")
        finally:
            safe_update(self.enable_ui) # Ensure UI is re-enabled

    def enable_ui(self):
        """ Safely re-enables UI elements after operation completes or stops using try-except for each widget. """
        widgets_to_enable = [
            (self.run_button, "normal"),
            (self.folder_entry, "normal"),
            (self.browse_button, "normal"),
            (self.mode_dropdown, "normal"),
            (self.ignore_entry, "normal"),
            (self.ignore_ext_entry, "normal"),
            (self.target_entry, "normal"),
            (self.target_ext_entry, "normal"),
            (self.stop_button, "disabled"), # Stop always disabled when not running
        ]

        # Handle open_output_button separately based on last_output_path
        open_output_state = "disabled"
        if last_output_path and Path(last_output_path).exists():
            open_output_state = "normal"
        widgets_to_enable.append((self.open_output_button, open_output_state))

        for widget, state in widgets_to_enable:
            try:
                # Check if the widget object itself exists and hasn't been destroyed
                if widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                    widget.configure(state=state)
            except Exception as e:
                # Log error if a widget fails to re-enable, but continue with others
                print(f"Warning: Failed to re-enable widget {widget}: {e}")
                # Optionally update status bar here too, but might be too noisy
                # self.update_status(f"Warning: UI element update failed for {widget}")

        self.generation_thread = None # Clear thread reference


    def on_stop(self):
        # (No changes needed in this method)
        global stop_requested
        if self.generation_thread and self.generation_thread.is_alive():
            stop_requested = True
            self.stop_button.configure(state="disabled")
            self.update_status("Stop requested, attempting to halt generation...")
        else:
             self.update_status("Nothing to stop (no generation process running).")

    def ask_open_output_folder(self, output_dir):
        # (No changes needed in this method)
        if messagebox.askyesno("Success", f"Output successfully generated.\n\nDo you want to open the outputs folder?"):
             self.open_folder(output_dir)

    def open_output(self):
        # (No changes needed in this method)
        folder_to_open = None
        if last_output_path and os.path.exists(last_output_path):
            folder_to_open = os.path.dirname(last_output_path)
            self.update_status(f"Opening last output folder: {folder_to_open}")
        else:
            output_dir = Path(get_outputs_folder_path())
            if output_dir.exists() and output_dir.is_dir():
                 folder_to_open = output_dir
                 self.update_status(f"Opening default output folder: {folder_to_open}")
            else:
                 self.update_status("No output generated yet or output folder not found.")
                 messagebox.showinfo("Info", "No output has been generated in this session, or the output folder cannot be found.")
                 return

        if folder_to_open:
             self.open_folder(folder_to_open)

    def open_folder(self, folder_path):
        # (No changes needed in this method)
        folder_path_str = str(folder_path)
        try:
            if sys.platform.startswith('win'):
                os.startfile(folder_path_str)
            elif sys.platform.startswith('darwin'):
                subprocess.call(["open", folder_path_str])
            else:
                subprocess.call(["xdg-open", folder_path_str])
        except Exception as e:
            error_msg = f"Error opening folder '{folder_path_str}': {e}"
            self.update_status(error_msg)
            messagebox.showerror("Error", error_msg)

    def on_closing(self):
        # (No changes needed in this method)
        global stop_requested, app
        if self.generation_thread and self.generation_thread.is_alive():
             if messagebox.askyesno("Exit Confirmation", "Generation is in progress. Are you sure you want to exit? This may leave an incomplete output file."):
                 stop_requested = True
                 self.update_status("Exit requested during generation, stopping...")
                 app = None
                 self.destroy()
             else:
                 return
        else:
             app = None
             self.destroy()

# ======================================================================
# Main Execution Block
# ======================================================================
if __name__ == "__main__":
    # Set CustomTkinter appearance
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    main_app = FileTreeBuilderApp()
    main_app.mainloop()