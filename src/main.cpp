// main.cpp
#include "gui.h"
#include <FL/Fl.H>
#include <windows.h>
#include <shlwapi.h>
#pragma comment(lib, "Shlwapi.lib") // For any Windows API functions if needed

int main(int argc, char **argv) {
    Fl::lock(); // Enable thread-safe updates

    create_gui();

    // Center the window on screen
    int screen_w = GetSystemMetrics(SM_CXSCREEN);
    int screen_h = GetSystemMetrics(SM_CYSCREEN);
    center_window(screen_w, screen_h);

    win->show(argc, argv);

    Fl::add_timeout(0.5, check_worker_status);

    int ret = Fl::run();

    if(worker_thread.joinable()){
         worker_thread.join();
    }

    return ret;
}
