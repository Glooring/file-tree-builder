// gui.cpp
#include "gui.h"
#include "file_tree.h"
#include <FL/Fl.H>
#include <FL/Fl_Native_File_Chooser.H>
#include <FL/fl_ask.H>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <ctime>
#include <windows.h>
#include <shellapi.h>

namespace fs = std::filesystem;

// ----------------------------------------------------------------------
// Custom window class to intercept background clicks and remove focus
class MyWindow : public Fl_Window {
public:
    MyWindow(int X, int Y, int W, int H, const char* L = 0) : Fl_Window(X, Y, W, H, L) {}
    int handle(int event) override {
        if (event == FL_PUSH) {
            // If the click is on the window background, take focus so that no widget remains highlighted
            if (Fl::belowmouse() == this) {
                this->take_focus();
            }
        }
        return Fl_Window::handle(event);
    }
};

// ----------------------------------------------------------------------
// Custom button class to accept drag & drop for folders.
class DropButton : public Fl_Button {
public:
    DropButton(int X, int Y, int W, int H, const char* L = 0) : Fl_Button(X, Y, W, H, L) {}
    int handle(int event) override {
        switch (event) {
            case FL_DND_ENTER:
            case FL_DND_DRAG:
                return 1; // Accept drag events
            case FL_DND_RELEASE: {
                const char* dropped = Fl::event_text();
                if (dropped && dropped[0] != '\0') {
                    fs::path p(dropped);
                    // If dropped path exists and is a directory, replace the text field content with it
                    if (fs::exists(p) && fs::is_directory(p)) {
                        inp_folder->value(p.string().c_str());
                    }
                }
                return 1;
            }
            default:
                return Fl_Button::handle(event);
        }
    }
};

// ----------------------------------------------------------------------
// Global widget declarations
Fl_Window* win = nullptr;
Fl_Input* inp_folder = nullptr;
Fl_Button* btn_browse = nullptr; // Will be instantiated as DropButton
Fl_Choice* choice_mode = nullptr;
Fl_Input* inp_filter1 = nullptr;
Fl_Input* inp_filter2 = nullptr;
Fl_Button* btn_run = nullptr;
Fl_Button* btn_stop = nullptr;

std::thread worker_thread;
std::atomic<bool> stop_flag(false);
std::atomic<bool> running_flag(false);

// To remember the folder that was processed (set in run_button_cb)
static std::string g_processed_folder;

// ----------------------------------------------------------------------
// 1) update_output (stub)
void update_output(const std::string& message) {
    // For debugging, you can uncomment the next line:
    // std::clog << message << std::endl;
}

// ----------------------------------------------------------------------
// 2) mode_choice_cb
// When mode is changed, reset the textbox texts and remove focus from the dropdown.
void mode_choice_cb(Fl_Widget*, void*) {
    int mode_index = choice_mode->value(); // 0 = Classic, 1 = Target
    if (mode_index == 0) {
        inp_filter1->label("Ignore folders/files:");
        inp_filter2->label("Ignore extensions:");
    } else {
        inp_filter1->label("Target folders/files:");
        inp_filter2->label("Target extensions:");
    }
    // Reset the textbox values
    inp_filter1->value("");
    inp_filter2->value("");
    // Transfer focus to the window to remove the blue highlight from the dropdown
    Fl::focus(win);
    win->redraw();
}

// ----------------------------------------------------------------------
// 3) browse_button_cb
// Uses the native folder chooser dialog.
void browse_button_cb(Fl_Widget*, void*) {
    Fl_Native_File_Chooser fnfc;
    fnfc.title("Select Folder");
    fnfc.type(Fl_Native_File_Chooser::BROWSE_DIRECTORY);
    const char* initialDir = getenv("USERPROFILE");
    if (!initialDir) initialDir = ".";
    fnfc.directory(initialDir);
    
    if (fnfc.show() == 0) {
        inp_folder->value(fnfc.filename());
    } else {
        //fl_alert("Browse cancelled or error occurred.");
    }
}

// ----------------------------------------------------------------------
// 4) run_button_cb
void run_button_cb(Fl_Widget*, void*) {
    if (running_flag.load()) {
        fl_message("Process is already running.");
        return;
    }
    std::string folderPath = inp_folder->value();
    if (folderPath.empty()) {
        fl_alert("Please select or enter a folder path.");
        return;
    }
    // Save the processed folder path for later naming of the output file
    g_processed_folder = folderPath;
    
    bool targetMode = (choice_mode->value() == 1);
    std::string filter1 = inp_filter1->value();
    std::string filter2 = inp_filter2->value();

    // Disable controls
    inp_folder->deactivate();
    btn_browse->deactivate();
    choice_mode->deactivate();
    inp_filter1->deactivate();
    inp_filter2->deactivate();
    btn_run->deactivate();
    btn_stop->activate();

    stop_flag.store(false);
    running_flag.store(true);

    // Start the worker thread (run_file_tree_builder will create "output.txt" in the current directory)
    worker_thread = std::thread([folderPath, targetMode, filter1, filter2]() {
         run_file_tree_builder(folderPath, targetMode, filter1, filter2, update_output, stop_flag);
         running_flag.store(false);
    });
}

// ----------------------------------------------------------------------
// 5) stop_button_cb
void stop_button_cb(Fl_Widget*, void*) {
    if (running_flag.load()) {
        update_output("Stop signal sent. Process will terminate...");
        stop_flag.store(true);
        btn_stop->deactivate();
    }
}

// ----------------------------------------------------------------------
// 6) check_worker_status
void check_worker_status(void*) {
    if (!running_flag.load()) {
        if (!btn_run->active()) {
            // Re-enable controls
            inp_folder->activate();
            btn_browse->activate();
            choice_mode->activate();
            inp_filter1->activate();
            inp_filter2->activate();
            btn_run->activate();
            btn_stop->deactivate();

            if (worker_thread.joinable()) {
                worker_thread.join();
            }
            // After processing, automatically save the output file
            save_output_automatically();
        }
    }
    Fl::repeat_timeout(0.5, check_worker_status);
}

// ----------------------------------------------------------------------
// 7) save_output_automatically
// Saves "output.txt" automatically in the "outputs" folder (located in the same directory as the .exe).
// The file name is formed as: [folderName]_hierarchy.txt.
// If that file already exists, appends the current datetime string (YYYYMMDDHHMMSS) to create a unique name.
void save_output_automatically() {
    fs::path exeDir = fs::current_path(); // Assumes the current path is the exe's directory
    fs::path outputsDir = exeDir / "outputs";
    if (!fs::exists(outputsDir)) {
        try {
            fs::create_directory(outputsDir);
        } catch (const std::exception& ex) {
            fl_alert("Error creating outputs folder:\n%s", ex.what());
            return;
        }
    }

    fs::path inputFolder(g_processed_folder);
    std::string folderName = inputFolder.filename().string();
    if (folderName.empty())
        folderName = "output";

    std::string base = folderName + "_hierarchy";
    std::string ext = ".txt";
    fs::path dest = outputsDir / (base + ext);

    // If the file already exists, append the current datetime.
    if (fs::exists(dest)) {
        // Get current datetime as a string (YYYYMMDDHHMMSS)
        std::time_t now = std::time(nullptr);
        std::tm *ltm = std::localtime(&now);
        char dt[20];
        std::strftime(dt, sizeof(dt), "%Y%m%d%H%M%S", ltm);
        std::string datetime(dt);

        base += "_" + datetime;
        dest = outputsDir / (base + ext);
        // In case this file also exists, repeatedly append the datetime until the name is unique.
        while (fs::exists(dest)) {
            base += "_" + datetime;
            dest = outputsDir / (base + ext);
        }
    }

    fs::path src("output.txt");
    if (!fs::exists(src)) {
        fl_alert("No 'output.txt' found. Nothing to save.");
        return;
    }
    try {
        fs::copy_file(src, dest, fs::copy_options::overwrite_existing);
    } catch (const std::exception& ex) {
        fl_alert("Error saving output file:\n%s", ex.what());
        return;
    }

    // Show a message indicating success and ask if the user wants to open the folder in File Explorer.
    int choice = fl_choice(
        ("Output file successfully generated at:\n" + dest.string() + "\n\nOpen the folder in File Explorer?").c_str(),
        "No", "Yes", 0);
    if (choice == 1) {
        ShellExecuteA(NULL, "open", outputsDir.string().c_str(), NULL, NULL, SW_SHOWNORMAL);
    }
}

// ----------------------------------------------------------------------
// 8) create_gui
// Uses the custom MyWindow class for background clicks, and the Browse button is instantiated as a DropButton.
void create_gui() {
    win = new MyWindow(650, 230, 650, 230, "File Tree Builder");
    win->begin();

    // 1. Input for folder path and Browse button
    inp_folder = new Fl_Input(150, 20, 400, 25, "Folder Path:");
    btn_browse = new DropButton(560, 20, 80, 25, "Browse");
    btn_browse->callback(browse_button_cb);

    // 2. Dropdown "Mode"
    static Fl_Menu_Item mode_items[] = {
        {"Classic", 0, 0, 0},
        {"Target",  0, 0, 0},
        {0}
    };
    choice_mode = new Fl_Choice(150, 60, 150, 25, "Mode:");
    choice_mode->menu(mode_items);
    choice_mode->callback(mode_choice_cb);
    choice_mode->value(0); // Default to "Classic"

    // 3. Inputs for filters
    inp_filter1 = new Fl_Input(150, 100, 400, 25, "Ignore folders/files:");
    inp_filter2 = new Fl_Input(150, 140, 400, 25, "Ignore extensions:");

    // 4. Run and Stop buttons
    btn_run = new Fl_Button(150, 180, 150, 30, "Run");
    btn_run->callback(run_button_cb);
    btn_stop = new Fl_Button(320, 180, 150, 30, "Stop");
    btn_stop->callback(stop_button_cb);
    btn_stop->deactivate();

    win->end();
    win->resizable(nullptr);
}

// ----------------------------------------------------------------------
// 9) center_window
void center_window(int screen_w, int screen_h) {
    win->position((screen_w - win->w()) / 2, (screen_h - win->h()) / 2);
}
