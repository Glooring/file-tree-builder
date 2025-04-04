// file_tree.cpp
#include "file_tree.h"
#include <windows.h>
#include <fstream>
#include <sstream>
#include <iostream>
#include <vector>
#include <set>
#include <algorithm>
#include <chrono>
#include <thread>
#include <string>
#include <cctype>

// We assume stop_flag is declared externally (in your gui code)
extern std::atomic<bool> stop_flag;

// -----------------------
// Helper: split_to_set
// -----------------------
std::set<std::string> split_to_set(const std::string& input) {
    std::set<std::string> result;
    std::istringstream iss(input);
    std::string token;
    while (std::getline(iss, token, '|')) {
        token.erase(0, token.find_first_not_of(" \t"));
        token.erase(token.find_last_not_of(" \t") + 1);
        if(!token.empty()){
            result.insert(token);
        }
    }
    return result;
}

// -----------------------
// Helper: read_file_content
// -----------------------
std::string read_file_content(const std::string& filepath) {
    std::ifstream ifs(filepath, std::ios::in);
    if(!ifs) {
        return "Error reading file.";
    }
    std::stringstream ss;
    ss << ifs.rdbuf();
    return ss.str();
}

// -----------------------
// Internal structure for directory entries
// -----------------------
struct DirEntry {
    std::string name;
    bool isDirectory;
};

// -----------------------
// Fast version of classic mode tree building using Windows API
// -----------------------
void build_classic_tree_lines_fast(const std::string& current, const std::string& root,
                                   const std::set<std::string>& ignored_folders,
                                   const std::string& prefix,
                                   std::vector<std::string>& lines) {
    if (stop_flag.load()) return;
    std::string searchPath = current + "\\*";
    WIN32_FIND_DATAA ffd;
    HANDLE hFind = FindFirstFileExA(searchPath.c_str(), FindExInfoBasic, &ffd,
                                     FindExSearchNameMatch, NULL, FIND_FIRST_EX_LARGE_FETCH);
    if (hFind == INVALID_HANDLE_VALUE)
        return;
    
    std::vector<DirEntry> entries;
    do {
        if (stop_flag.load()) break;
        std::string name = ffd.cFileName;
        if (name == "." || name == "..")
            continue;
        bool isDir = (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        entries.push_back({name, isDir});
    } while (FindNextFileA(hFind, &ffd));
    FindClose(hFind);
    
    // Sort: directories first, then files, alphabetically
    std::sort(entries.begin(), entries.end(), [](const DirEntry& a, const DirEntry& b) {
        if (a.isDirectory != b.isDirectory)
            return a.isDirectory > b.isDirectory;
        return a.name < b.name;
    });
    
    for (size_t i = 0; i < entries.size(); ++i) {
        if (stop_flag.load()) break;
        bool isLast = (i == entries.size() - 1);
        std::string connector = isLast ? "└── " : "├── ";
        std::string line = prefix + connector + entries[i].name;
        lines.push_back(line);
        if (entries[i].isDirectory) {
            // If the directory is in the ignore list, skip it.
            if (ignored_folders.find(entries[i].name) != ignored_folders.end())
                continue;
            std::string newPrefix = prefix + (isLast ? "    " : "│   ");
            std::string nextPath = current + "\\" + entries[i].name;
            build_classic_tree_lines_fast(nextPath, root, ignored_folders, newPrefix, lines);
        }
    }
}

// -----------------------
// Fast version of target mode tree building using Windows API
// -----------------------
bool build_target_tree_lines_fast(const std::string& current, const std::string& root,
                                    const std::set<std::string>& target_folders,
                                    const std::set<std::string>& target_files,
                                    const std::set<std::string>& target_extensions,
                                    const std::string& prefix,
                                    std::vector<std::string>& lines) {
    if (stop_flag.load()) return false;
    std::string searchPath = current + "\\*";
    WIN32_FIND_DATAA ffd;
    HANDLE hFind = FindFirstFileExA(searchPath.c_str(), FindExInfoBasic, &ffd,
                                     FindExSearchNameMatch, NULL, FIND_FIRST_EX_LARGE_FETCH);
    if (hFind == INVALID_HANDLE_VALUE)
        return false;
    
    std::vector<DirEntry> entries;
    do {
        if (stop_flag.load()) break;
        std::string name = ffd.cFileName;
        if (name == "." || name == "..")
            continue;
        bool isDir = (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        entries.push_back({name, isDir});
    } while (FindNextFileA(hFind, &ffd));
    FindClose(hFind);
    
    std::sort(entries.begin(), entries.end(), [](const DirEntry& a, const DirEntry& b) {
        if (a.isDirectory != b.isDirectory)
            return a.isDirectory > b.isDirectory;
        return a.name < b.name;
    });
    
    bool hasMatch = false;
    for (size_t i = 0; i < entries.size(); ++i) {
        if (stop_flag.load()) return false;
        bool isLast = (i == entries.size() - 1);
        std::string connector = isLast ? "└── " : "├── ";
        std::string line = prefix + connector + entries[i].name;
        std::string fullPath = current + "\\" + entries[i].name;
        if (entries[i].isDirectory) {
            std::vector<std::string> subLines;
            std::string newPrefix = prefix + (isLast ? "    " : "│   ");
            bool childMatch = build_target_tree_lines_fast(fullPath, root, target_folders, target_files, target_extensions, newPrefix, subLines);
            // Include the directory if its name is in target_folders or if any child matches.
            if (target_folders.find(entries[i].name) != target_folders.end() || childMatch) {
                lines.push_back(line);
                lines.insert(lines.end(), subLines.begin(), subLines.end());
                hasMatch = true;
            }
        } else {
            // For files: compute relative path.
            std::string relPath;
            if (fullPath.find(root) == 0) {
                relPath = fullPath.substr(root.size());
                if (!relPath.empty() && (relPath[0] == '\\' || relPath[0] == '/'))
                    relPath.erase(0,1);
            } else {
                relPath = fullPath;
            }
            bool fileMatch = true;
            if (!target_files.empty()) {
                if (target_files.find(entries[i].name) == target_files.end() &&
                    target_files.find(relPath) == target_files.end()) {
                    fileMatch = false;
                }
            }
            if (fileMatch && !target_extensions.empty()) {
                size_t pos = entries[i].name.rfind('.');
                std::string ext = (pos != std::string::npos) ? entries[i].name.substr(pos) : "";
                if (target_extensions.find(ext) == target_extensions.end())
                    fileMatch = false;
            }
            if (fileMatch) {
                lines.push_back(line);
                hasMatch = true;
            }
        }
    }
    return hasMatch;
}

// -----------------------
// Fast version of traverse_files_recursively for classic mode using Windows API
// -----------------------
void traverse_files_recursively_fast(const std::string& current, const std::string& root,
                                       const std::set<std::string>& ignored_folders,
                                       std::vector<std::string>& file_list) {
    if (stop_flag.load()) return;
    std::string searchPath = current + "\\*";
    WIN32_FIND_DATAA ffd;
    HANDLE hFind = FindFirstFileExA(searchPath.c_str(), FindExInfoBasic, &ffd,
                                     FindExSearchNameMatch, NULL, FIND_FIRST_EX_LARGE_FETCH);
    if (hFind == INVALID_HANDLE_VALUE)
        return;
    do {
        if (stop_flag.load()) break;
        std::string name = ffd.cFileName;
        if (name == "." || name == "..")
            continue;
        std::string fullPath = current + "\\" + name;
        if (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (ignored_folders.find(name) != ignored_folders.end())
                continue;
            traverse_files_recursively_fast(fullPath, root, ignored_folders, file_list);
        } else {
            std::string relPath;
            if (fullPath.find(root) == 0) {
                relPath = fullPath.substr(root.size());
                if (!relPath.empty() && (relPath[0] == '\\' || relPath[0] == '/'))
                    relPath.erase(0,1);
            } else {
                relPath = fullPath;
            }
            file_list.push_back(relPath);
        }
    } while (FindNextFileA(hFind, &ffd));
    FindClose(hFind);
}

// -----------------------
// Fast version of traverse_target_files_recursively for target mode using Windows API
// -----------------------
void traverse_target_files_recursively_fast(const std::string& current, const std::string& root,
                                              const std::set<std::string>& target_folders,
                                              const std::set<std::string>& target_files,
                                              const std::set<std::string>& target_extensions,
                                              std::vector<std::string>& file_list) {
    if (stop_flag.load()) return;
    std::string searchPath = current + "\\*";
    WIN32_FIND_DATAA ffd;
    HANDLE hFind = FindFirstFileExA(searchPath.c_str(), FindExInfoBasic, &ffd,
                                     FindExSearchNameMatch, NULL, FIND_FIRST_EX_LARGE_FETCH);
    if (hFind == INVALID_HANDLE_VALUE)
        return;
    do {
        if (stop_flag.load()) break;
        std::string name = ffd.cFileName;
        if (name == "." || name == "..")
            continue;
        std::string fullPath = current + "\\" + name;
        if (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            traverse_target_files_recursively_fast(fullPath, root, target_folders, target_files, target_extensions, file_list);
        } else {
            std::string relPath;
            if (fullPath.find(root) == 0) {
                relPath = fullPath.substr(root.size());
                if (!relPath.empty() && (relPath[0] == '\\' || relPath[0] == '/'))
                    relPath.erase(0,1);
            } else {
                relPath = fullPath;
            }
            bool fileMatch = true;
            if (!target_files.empty()) {
                if (target_files.find(name) == target_files.end() &&
                    target_files.find(relPath) == target_files.end()) {
                    fileMatch = false;
                }
            }
            if (fileMatch && !target_extensions.empty()) {
                size_t pos = name.rfind('.');
                std::string ext = (pos != std::string::npos) ? name.substr(pos) : "";
                if (target_extensions.find(ext) == target_extensions.end())
                    fileMatch = false;
            }
            if (fileMatch && !target_folders.empty()) {
                bool folderMatch = false;
                // Split relPath by '\' and check if any part is in target_folders.
                size_t start = 0;
                while (true) {
                    size_t pos = relPath.find('\\', start);
                    std::string part = (pos == std::string::npos) ? relPath.substr(start) : relPath.substr(start, pos - start);
                    if (target_folders.find(part) != target_folders.end()) {
                        folderMatch = true;
                        break;
                    }
                    if (pos == std::string::npos)
                        break;
                    start = pos + 1;
                }
                if (!folderMatch)
                    fileMatch = false;
            }
            if (fileMatch) {
                file_list.push_back(relPath);
            }
        }
    } while (FindNextFileA(hFind, &ffd));
    FindClose(hFind);
}

// -----------------------
// Main function: run_file_tree_builder
// -----------------------
void run_file_tree_builder(const std::string& folderPath, bool targetMode, const std::string& filter1,
                           const std::string& filter2, LogCallback logCallback, std::atomic<bool>& stopFlag) {
    auto startTime = std::chrono::high_resolution_clock::now();
    std::string root = folderPath;
    // Validate that the root exists using GetFileAttributesA.
    DWORD attr = GetFileAttributesA(root.c_str());
    if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        logCallback("Error: The provided path is not a valid directory.");
        return;
    }
    
    std::vector<std::string> tree_lines;
    std::vector<std::string> file_list;
    if (targetMode) {
        std::set<std::string> target_folders = split_to_set(filter1);
        std::set<std::string> target_files = split_to_set(filter1); // Using the same input for folders and files
        std::set<std::string> target_extensions = split_to_set(filter2);
        build_target_tree_lines_fast(root, root, target_folders, target_files, target_extensions, "", tree_lines);
        traverse_target_files_recursively_fast(root, root, target_folders, target_files, target_extensions, file_list);
    } else {
        std::set<std::string> ignored_folders = split_to_set(filter1);
        std::set<std::string> ignored_files = split_to_set(filter1); // Using the same input
        std::set<std::string> ignored_extensions = split_to_set(filter2);
        build_classic_tree_lines_fast(root, root, ignored_folders, "", tree_lines);
        traverse_files_recursively_fast(root, root, ignored_folders, file_list);
        // Filter file_list: remove files whose names are in ignored_files or have ignored extensions.
        std::vector<std::string> filtered_files;
        for (const auto& f : file_list) {
            size_t pos = f.find_last_of("\\/");
            std::string filename = (pos == std::string::npos) ? f : f.substr(pos + 1);
            if (ignored_files.find(filename) != ignored_files.end())
                continue;
            size_t dot = filename.rfind('.');
            std::string ext = (dot != std::string::npos) ? filename.substr(dot) : "";
            if (ignored_extensions.find(ext) != ignored_extensions.end())
                continue;
            filtered_files.push_back(f);
        }
        file_list = filtered_files;
    }
    
    // Build the output content (same layout as before)
    std::stringstream output;
    output << "Hierarchy of folders and files:\n";
    for (const auto& line : tree_lines) {
        output << line << "\n";
    }
    output << "\nContents of files:\n\n";
    for (const auto& f : file_list) {
        std::string fullPath = root + "\\" + f;
        output << f << ":\n";
        output << "```\n";
        std::string content = read_file_content(fullPath);
        output << content << "\n";
        output << "```\n\n";
    }
    
    // Write the output to "output.txt" in the current (exe) directory
    std::string outputPath = "output.txt";
    std::ofstream ofs(outputPath);
    if (ofs) {
        ofs << output.str();
        ofs.close();
        logCallback("Output successfully written to '" + outputPath + "'.");
    } else {
        logCallback("Error writing to output file.");
    }
    
    auto endTime = std::chrono::high_resolution_clock::now();
    double duration = std::chrono::duration<double>(endTime - startTime).count();
    std::stringstream timeMsg;
    timeMsg << "Process finished in " << duration << " seconds.";
    logCallback(timeMsg.str());
}
