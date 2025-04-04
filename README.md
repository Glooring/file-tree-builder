# 📁 FileTreeBuilder

**FileTreeBuilder** is a fast, portable, and modern C++ desktop GUI application that generates a complete hierarchical representation of folders and files—including file contents—into a neatly structured `.txt` file.

It features a clean FLTK-based interface, drag-and-drop folder input, smart output file naming, and two powerful scanning modes: Classic and Target.

---

## 🔧 Features

- ✅ **Modern GUI** built using FLTK (thread-safe, responsive)
- 🚀 **High-speed traversal** using native Windows API (`FindFirstFileExA + LARGE_FETCH`)
- 📂 **Drag & Drop folder input**
- 🧠 **Smart filters** (ignore or target specific folders/files/extensions)
- 📄 **File contents embedded** with Markdown-style formatting
- 💾 **Output saved automatically** to `outputs/` with unique file naming
- 🗂️ **Output format**:
  ```
  Hierarchy of folders and files:
  ├── src
  │   ├── main.cpp
  │   └── file_tree.cpp
  ...

  Contents of files:

  src/main.cpp:
  ```
  file content
  ```
  ```

---

## 🖥️ GUI Overview

- **Folder Path** – select or drag a folder
- **Mode** – `Classic` (ignore) or `Target` (include-only)
- **Filters** – enter folder/file names and extensions separated by `|`
- **Run / Stop** – start or interrupt generation
- ✅ On completion, you'll be asked if you want to open the `outputs/` folder

---

## 📦 Folder Structure

```
.
├── file-tree-builder-v1.0.0
│   ├── FileTreeBuilder.exe         # Portable GUI application
│   ├── bin/                        # Place for any external tools if needed
│   ├── outputs/                    # Generated .txt files go here
│   ├── libfltk-1.4.dll             # Runtime FLTK DLLs
│   ├── libgcc_s_seh-1.dll
│   ├── libstdc++-6.dll
│   └── libwinpthread-1.dll
├── src/
│   ├── main.cpp                    # Entry point
│   ├── gui.cpp / gui.h            # GUI layout and logic
│   ├── file_tree.cpp / .h         # Core tree generation logic
├── compile_gui.bat                # One-click build script (via MSYS2 MinGW + g++)
```

---

## 🛠️ How to Build

**Requirements**:
- Windows OS
- MSYS2 with MinGW-w64
- `g++`, `fltk`, `make` (already configured in `compile_gui.bat`)

### 🔨 Build in one click:
```bash
compile_gui.bat
```
This will:
- Compile all sources
- Create `file-tree-builder-v1.0.0/`
- Copy required DLLs next to the `.exe`

The resulting `FileTreeBuilder.exe` is portable and can be run on any compatible Windows machine.

---

## ⚙️ Modes Explained

### 🔹 Classic Mode
- Input:
  - Folder/File names to **ignore**
  - Extensions to **ignore**
- Output:
  - Full tree without ignored content

### 🔹 Target Mode
- Input:
  - Folder/File names to **include**
  - Extensions to **include**
- Output:
  - Only tree and contents that match filters

---

## 📤 Output Naming & Saving

- Output file format: `foldername_hierarchy.txt`
- Saved in: `file-tree-builder-v1.0.0/outputs/`
- If file exists:
  - Appends current datetime (e.g. `myproject_hierarchy_20250404193012.txt`)
  - Ensures unique filename

---

## 💡 Example Use Case

1. Drag your `project/` folder into the GUI
2. Choose:
   - `Classic` → Ignore `.git|build`
   - `Target` → Include only `src|main.cpp|.cpp|.h`
3. Click **Run**
4. View output or open the folder when prompted

---

## 🧪 Tested On

- ✅ Windows 11 / 10
- ✅ MSYS2 (MinGW-w64)
- ✅ Screen resolutions up to 4K (resizable-ready)

---

## 📜 License

MIT License — free to use, share and modify.