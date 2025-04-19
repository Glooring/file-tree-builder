# 📁 File Tree Builder  <sub>(Python GUI)</sub>

*A modern GUI tool that snapshots any folder into a tidy Markdown‑style `.txt` – hierarchy first, optionally followed by every file’s source.*

<table>
  <tr><th>💻 Built with</th><td>Python 3.8+ · <a href="https://github.com/TomSchimansky/CustomTkinter">CustomTkinter</a> · <code>tkinter</code> · PyInstaller</td></tr>
  <tr><th>🏁 Platforms</th><td>Windows · macOS · Linux</td></tr>
  <tr><th>🔖 License</th><td>MIT</td></tr>
</table>

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Quick Start](#quickstart)  
4. [Scan Modes](#scanmodes)  
5. [Filters & Ignore Rules](#filtersignorerules)  
6. [Output Format](#outputformat)  
7. [Project Layout](#projectlayout)  
8. [Build the EXE](#buildtheexe)  
9. [Download Release](#downloadrelease)  
10. [Troubleshooting / FAQ](#troubleshootingfaq)  

---

## Overview

**File Tree Builder** lets you document any directory in seconds:

- **Hierarchy‑only** (fast) or **Hierarchy + file contents** (complete snapshot)  
- Live progress log – UI never freezes (background thread)  
- Configurable via JSON – no code edits needed  
- Exports a single Markdown‑ready `.txt`, ideal for wikis, issues, docs

---

## Features

|  |  |
|---|---|
| **✨ Polished GUI**      | Dark / Light theme (CustomTkinter) + drag‑and‑drop (Windows `windnd`) |
| **⚡ Async engine**      | Background worker, safe **Stop** button |
| **🗂 Three scan modes**  | *Classic*, *Target*, *No Content* |
| **🔍 Smart filters**     | Pipe‑separated patterns (`foo|bar|*.log`) + separate extension list |
| **📝 Markdown output**   | Code‑fences auto‑tagged via `helpers/lang_map.json` |
| **🔄 Undo/Redo**         | All text fields support <kbd>Ctrl Z</kbd>/<kbd>Y</kbd> |
| **📥 Open output**       | One‑click “Open output folder” button |
| **🔌 100 % configurable**| Edit JSON lists, restart – no rebuild needed |

---

## Quick Start

```bash
# 1 · install dependencies
pip install customtkinter windnd   # windnd ⇒ optional (Windows only)

# 2 · run from source
python file-tree-builder.py
```

Or double‑click **FileTreeBuilder.exe** (after packaging).

---

## Scan Modes

| Mode          | Purpose                         | Filters used              | Contents exported? |
|---------------|---------------------------------|---------------------------|--------------------|
| **Classic**   | Everything except ignored items | Ignore Items + Ignore Exts | ✅ Yes            |
| **Target**    | Only what you list              | Target Items + Target Exts | ✅ Yes (targets)  |
| **No Content**| Fast tree snapshot              | Ignore Items + Ignore Exts | ❌ Skipped        |

---

## Filters & Ignore Rules

Defaults load from JSON files at startup.

| File | Description |
|------|-------------|
| **ignore_items.json** | File/folder names or wildcard patterns (e.g. `*.min.js`).<br>They appear in the tree, but their **content is hidden**. |
| **ignore_exts.json**  | Extensions *without* dot (e.g. `log`, `tmp`). Files are completely excluded. |
| **lang_map.json**     | Maps `.ext → language` for Markdown fences. Extend it freely. |

**Examples**  
- Hide all `.log` files but still list them in tree:  
  - **Ignore Exts ➡** `log`  
- Hide `node_modules/` & `*.min.js`, but still show `build.log` without contents:  
  - **Ignore Items ➡** `node_modules|*.min.js|build.log`  
  - **Ignore Exts ➡** *(leave empty)*  

---

## Output Format

````text
Hierarchy of folders and files:

my-project                  ← root folder printed first
├── src
│   └── main.py
└── README.md

Contents of files:

src/main.py:
```python
print("hello")
```
````

- Blank line separates **hierarchy** from **contents**  
- Language hints are auto-added using `lang_map.json`

---

## Project Layout

📦 From source:
```text
.
├─ helpers/               # JSON config files
│  ├─ ignore_items.json
│  ├─ ignore_exts.json
│  └─ lang_map.json
├─ outputs/               # output .txt files
├─ file-tree-builder.py   # main app script
└─ README.md
```

📦 Packaged with PyInstaller (`--onedir`):
```text
FileTreeBuilder/
├─ outputs/                      # generated .txt files
├─ _internal/                    # Python runtime & bundled libs
│   └─ helpers/                  # JSON files live inside _internal
│       ├─ ignore_items.json
│       ├─ ignore_exts.json
│       └─ lang_map.json
└─ FileTreeBuilder.exe           # portable executable
```

---

## Build the EXE

```bat
pip install pyinstaller

pyinstaller ^
  --onedir ^
  --name FileTreeBuilder ^
  --noconsole ^
  --add-data "helpers;helpers" ^
  file-tree-builder.py
```

- For macOS/Linux: replace `;` with `:` in `--add-data`.
- This will copy `helpers/` next to the EXE inside `FileTreeBuilder/`.

---

## Download Release

Download the ready‑to‑run version from the [Releases](https://github.com/yourusername/yourrepo/releases) tab.

```
FileTreeBuilder.zip
└── FileTreeBuilder/
    ├── outputs/
    ├── _internal/
    │   └── helpers/
    │       ├── ignore_items.json
    │       ├── ignore_exts.json
    │       └── lang_map.json
    └── FileTreeBuilder.exe
```

✅ Just unzip and double‑click **FileTreeBuilder.exe**. No install needed.  
🛠 Works offline. Output goes in the included `outputs/` folder.

---

## Troubleshooting / FAQ

| Problem                          | Solution |
|----------------------------------|----------|
| Drag‑and‑drop not working        | `pip install windnd` (Windows only) |
| JSON files not found in EXE      | Use `--add-data "helpers;_internal/helpers"` and ensure path exists |
| "Permission denied" errors       | Run as admin or scan user-accessible folders |
| Output file is empty             | Review filters — likely everything was excluded |

---

## License

MIT License — free for personal & commercial use.

---

## Acknowledgements

- **CustomTkinter** – modern theming for Tkinter  
- **windnd** – drag-and-drop for Windows  
- **PyInstaller** – app packaging  
- Everyone who helped build open extension maps ❤️  