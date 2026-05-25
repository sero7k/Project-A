// toolkit.dll — Project A modding toolkit
// Console + OutputDebugString hooks + file logging
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <stdio.h>
#include <string>
#include <mutex>
#include <cstdint>
#include <tlhelp32.h>

static FILE* g_logfile = nullptr;
static char logpath_global[MAX_PATH] = {};

static void log_init()
{
    HMODULE hSelf = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCSTR)&log_init, &hSelf);
    char self_path[MAX_PATH];
    GetModuleFileNameA(hSelf, self_path, MAX_PATH);
    std::string dir(self_path);
    auto pos = dir.rfind('\\');
    if (pos != std::string::npos) dir = dir.substr(0, pos);
    strcpy_s(logpath_global, (dir + "\\toolkit.log").c_str());

    g_logfile = fopen(logpath_global, "w");
    if (g_logfile) {
        fprintf(g_logfile, "[toolkit] Log started %s %s\n", __DATE__, __TIME__);
        fprintf(g_logfile, "[toolkit] Log path: %s\n", logpath_global);
        fflush(g_logfile);
    }
}

static void log_msg(const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    if (g_logfile) { vfprintf(g_logfile, fmt, args); fflush(g_logfile); }
    va_end(args);
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
    fflush(stdout);
}

static FILE* g_conout = nullptr;

static void open_console()
{
    AllocConsole();
    SetConsoleTitleA("[Project A] Debug Console");

    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    CONSOLE_SCREEN_BUFFER_INFO csbi;
    if (GetConsoleScreenBufferInfo(hOut, &csbi)) {
        COORD size = { csbi.dwSize.X, 9999 };
        SetConsoleScreenBufferSize(hOut, size);
    }

    freopen_s(&g_conout, "CONOUT$", "w", stdout);
    freopen_s(&g_conout, "CONOUT$", "w", stderr);

    SetConsoleOutputCP(CP_UTF8);

    log_msg("[toolkit] ===== Project A Debug Console =====\n");
    log_msg("[toolkit] Build: %s %s\n", __DATE__, __TIME__);
}

struct Hook {
    void*    target   = nullptr;
    uint8_t  original[12]{};
    bool     installed = false;
};

static bool install_hook(Hook& h, void* target, void* detour)
{
    h.target = target;
    DWORD old;
    if (!VirtualProtect(target, 12, PAGE_EXECUTE_READWRITE, &old))
        return false;

    memcpy(h.original, target, 12);

    uint8_t* p = (uint8_t*)target;
    p[0] = 0x48; p[1] = 0xB8;
    memcpy(p + 2, &detour, 8);
    p[10] = 0xFF; p[11] = 0xE0;

    VirtualProtect(target, 12, old, &old);
    h.installed = true;
    return true;
}

static Hook g_hookA, g_hookW;
static std::mutex g_mtx;

static void WINAPI my_OutputDebugStringA(LPCSTR  lpOutputString);
static void WINAPI my_OutputDebugStringW(LPCWSTR lpOutputString);

static void print_dbg(const char* msg)
{
    std::string s(msg ? msg : "(null)");
    if (!s.empty() && s.back() == '\n') s.pop_back();
    if (!s.empty() && s.back() == '\r') s.pop_back();
    if (!s.empty())
        log_msg("[ODS] %s\n", s.c_str());
}

static void WINAPI my_OutputDebugStringA(LPCSTR lpOutputString)
{
    std::lock_guard<std::mutex> lk(g_mtx);
    print_dbg(lpOutputString);

    DWORD old;
    VirtualProtect(g_hookA.target, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy(g_hookA.target, g_hookA.original, 12);
    VirtualProtect(g_hookA.target, 12, old, &old);

    OutputDebugStringA(lpOutputString);

    VirtualProtect(g_hookA.target, 12, PAGE_EXECUTE_READWRITE, &old);
    uint8_t* p = (uint8_t*)g_hookA.target;
    p[0] = 0x48; p[1] = 0xB8;
    void* det = (void*)my_OutputDebugStringA;
    memcpy(p + 2, &det, 8);
    p[10] = 0xFF; p[11] = 0xE0;
    VirtualProtect(g_hookA.target, 12, old, &old);
}

static void WINAPI my_OutputDebugStringW(LPCWSTR lpOutputString)
{
    std::lock_guard<std::mutex> lk(g_mtx);
    if (lpOutputString) {
        int len = WideCharToMultiByte(CP_UTF8, 0, lpOutputString, -1, nullptr, 0, nullptr, nullptr);
        if (len > 0) {
            std::string narrow(len, '\0');
            WideCharToMultiByte(CP_UTF8, 0, lpOutputString, -1, &narrow[0], len, nullptr, nullptr);
            print_dbg(narrow.c_str());
        }
    }

    DWORD old;
    VirtualProtect(g_hookW.target, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy(g_hookW.target, g_hookW.original, 12);
    VirtualProtect(g_hookW.target, 12, old, &old);

    OutputDebugStringW(lpOutputString);

    VirtualProtect(g_hookW.target, 12, PAGE_EXECUTE_READWRITE, &old);
    uint8_t* p = (uint8_t*)g_hookW.target;
    p[0] = 0x48; p[1] = 0xB8;
    void* det = (void*)my_OutputDebugStringW;
    memcpy(p + 2, &det, 8);
    p[10] = 0xFF; p[11] = 0xE0;
    VirtualProtect(g_hookW.target, 12, old, &old);
}

static DWORD WINAPI toolkit_main(LPVOID)
{
    log_init();
    open_console();

    log_msg("[toolkit] PID: %lu\n", GetCurrentProcessId());

    HMODULE k32 = GetModuleHandleA("kernel32.dll");

    void* fnA = (void*)GetProcAddress(k32, "OutputDebugStringA");
    if (fnA && install_hook(g_hookA, fnA, (void*)my_OutputDebugStringA))
        log_msg("[toolkit] OutputDebugStringA hooked @ %p\n", fnA);
    else
        log_msg("[toolkit] WARNING: failed to hook OutputDebugStringA\n");

    void* fnW = (void*)GetProcAddress(k32, "OutputDebugStringW");
    if (fnW && install_hook(g_hookW, fnW, (void*)my_OutputDebugStringW))
        log_msg("[toolkit] OutputDebugStringW hooked @ %p\n", fnW);
    else
        log_msg("[toolkit] WARNING: failed to hook OutputDebugStringW\n");

    log_msg("[toolkit] Ready — watching for game output...\n");
    log_msg("[toolkit] ─────────────────────────────────────\n");

    while (true) {
        Sleep(30000);
    }

    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        HANDLE t = CreateThread(nullptr, 0, toolkit_main, nullptr, 0, nullptr);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
