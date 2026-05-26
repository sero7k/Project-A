// injector.exe — injects toolkit.dll into a running process by name
// Usage: injector.exe [process-name]   (default: ShooterClient.exe)
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <TlHelp32.h>
#include <stdio.h>
#include <string>

static DWORD find_pid(const char* name)
{
    // Convert name to wide for comparison (MinGW TlHelp32 exposes W variants)
    wchar_t wname[MAX_PATH];
    MultiByteToWideChar(CP_ACP, 0, name, -1, wname, MAX_PATH);

    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;

    PROCESSENTRY32W pe{ sizeof(pe) };
    DWORD pid = 0;
    if (Process32FirstW(snap, &pe)) {
        do {
            if (_wcsicmp(pe.szExeFile, wname) == 0) {
                pid = pe.th32ProcessID;
                break;
            }
        } while (Process32NextW(snap, &pe));
    }
    CloseHandle(snap);
    return pid;
}

static bool inject(DWORD pid, const char* dll_path)
{
    HANDLE proc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!proc) {
        printf("[injector] OpenProcess failed: %lu\n", GetLastError());
        return false;
    }

    size_t path_len = strlen(dll_path) + 1;
    LPVOID remote_buf = VirtualAllocEx(proc, nullptr, path_len,
                                       MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote_buf) {
        printf("[injector] VirtualAllocEx failed: %lu\n", GetLastError());
        CloseHandle(proc);
        return false;
    }

    WriteProcessMemory(proc, remote_buf, dll_path, path_len, nullptr);

    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    LPTHREAD_START_ROUTINE load_lib =
        (LPTHREAD_START_ROUTINE)GetProcAddress(k32, "LoadLibraryA");

    HANDLE t = CreateRemoteThread(proc, nullptr, 0, load_lib, remote_buf, 0, nullptr);
    if (!t) {
        printf("[injector] CreateRemoteThread failed: %lu\n", GetLastError());
        VirtualFreeEx(proc, remote_buf, 0, MEM_RELEASE);
        CloseHandle(proc);
        return false;
    }

    WaitForSingleObject(t, 5000);
    CloseHandle(t);
    VirtualFreeEx(proc, remote_buf, 0, MEM_RELEASE);
    CloseHandle(proc);
    return true;
}

int main(int argc, char* argv[])
{
    const char* target = "ShooterClient-Win64-Shipping.exe";

    // Build absolute path to toolkit dir (same dir as injector.exe)
    char self_path[MAX_PATH];
    GetModuleFileNameA(nullptr, self_path, MAX_PATH);
    std::string self_dir(self_path);
    auto pos = self_dir.rfind('\\');
    if (pos != std::string::npos) self_dir = self_dir.substr(0, pos);

    // Always inject toolkit.dll first, then any extra DLLs passed as args
    std::string toolkit_path = self_dir + "\\toolkit.dll";

    printf("[injector] Target  : %s\n", target);
    printf("[injector] DLL     : %s\n", toolkit_path.c_str());
    for (int i = 1; i < argc; i++)
        printf("[injector] Extra   : %s\n", argv[i]);

    // Wait for the process to appear (up to 30 s)
    printf("[injector] Waiting for process...\n");
    DWORD pid = 0;
    for (int i = 0; i < 60; i++) {
        pid = find_pid(target);
        if (pid) break;
        Sleep(500);
        if (i % 4 == 0) printf(".");
        fflush(stdout);
    }
    printf("\n");

    if (!pid) {
        printf("[injector] Process not found. Start the game first.\n");
        system("pause");
        return 1;
    }

    printf("[injector] Found PID %lu — injecting...\n", pid);

    // Give the process a moment to initialise before we inject
    Sleep(1500);

    if (inject(pid, toolkit_path.c_str()))
        printf("[injector] toolkit.dll injected!\n");
    else
        printf("[injector] toolkit.dll FAILED.\n");

    // Inject any extra DLLs passed as arguments (e.g. Dumper.dll)
    for (int i = 1; i < argc; i++) {
        Sleep(500);
        if (inject(pid, argv[i]))
            printf("[injector] %s injected!\n", argv[i]);
        else
            printf("[injector] %s FAILED.\n", argv[i]);
    }

    system("pause");
    return 0;
}
