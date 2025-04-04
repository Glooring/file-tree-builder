#pragma once
#include <string>
#include <functional>
#include <atomic>
#include <vector>

// The log callback is used to output messages (e.g., time taken)
using LogCallback = std::function<void(const std::string&)>;

// This function traverses the directory and writes a file tree into "output.txt".
void run_file_tree_builder(const std::string& folderPath,
                           bool targetMode,
                           const std::string& filter1,
                           const std::string& filter2,
                           LogCallback logCallback,
                           std::atomic<bool>& stopFlag);
