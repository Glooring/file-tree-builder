// gui.h
#pragma once

#include <FL/Fl_Window.H>
#include <FL/Fl_Input.H>
#include <FL/Fl_Button.H>
#include <FL/Fl_Choice.H>
#include <string>
#include <thread>
#include <atomic>

// Main window and widget declarations
extern Fl_Window* win;
extern Fl_Input* inp_folder;
extern Fl_Button* btn_browse; // This will be instantiated as a DropButton
extern Fl_Choice* choice_mode;
extern Fl_Input* inp_filter1;
extern Fl_Input* inp_filter2;
extern Fl_Button* btn_run;
extern Fl_Button* btn_stop;

// Worker thread and flags
extern std::thread worker_thread;
extern std::atomic<bool> stop_flag;
extern std::atomic<bool> running_flag;

// Function used by file_tree.cpp (stub – no GUI output)
void update_output(const std::string& message);

// Callbacks
void browse_button_cb(Fl_Widget*, void*);
void mode_choice_cb(Fl_Widget*, void*);
void run_button_cb(Fl_Widget*, void*);
void stop_button_cb(Fl_Widget*, void*);
void check_worker_status(void*);

// GUI creation and centering
void create_gui();
void center_window(int screen_w, int screen_h);

// Function for automatically saving the output file
void save_output_automatically();
