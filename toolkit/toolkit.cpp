// toolkit.dll v2 — Project A modding toolkit
// ODS hooks + UE4 GObjects scanner + UUID dumper
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <stdio.h>
#include <string>
#include <mutex>
#include <cstdint>
#include <vector>
#include <map>
#include <algorithm>

// ─── offsets from Dumper-7 SDK (Basic.hpp) ───────────────────────────────────
static constexpr uint64_t OFF_GOBJECTS     = 0x05C4FA08;
static constexpr uint64_t OFF_APPENDSTRING = 0x019DB1D0;
static constexpr uint64_t OFF_GWORLD       = 0x05D73188;
static constexpr uint64_t OFF_PROCESSEVENT = 0x1B8CB70;
static constexpr bool ENABLE_RANGE_CONTROLLER_REPAIR = false;

// ─── UE4 object flags ────────────────────────────────────────────────────────
static constexpr uint32_t RF_ClassDefaultObject = 0x00000010;
static constexpr uint32_t RF_ArchetypeObject    = 0x00000020;

// ─── ECharacterID (CharacterID_structs.hpp) ──────────────────────────────────
static const char* CharacterIDName(uint8_t id)
{
    switch (id) {
        case 0: return "Unknown";
        case 1: return "Phoenix";
        case 2: return "Jett(Wushu)";
        case 3: return "Viper(Pandemic)";
        case 4: return "Breach";
        case 5: return "Sova(Hunter)";
        case 6: return "Sage(Thorne)";
        case 7: return "Cypher(Gumshoe)";
        case 8: return "Omen(Wraith)";
        case 9: return "Brimstone(Sarge)";
        default: return "???";
    }
}

// ─── logging ─────────────────────────────────────────────────────────────────
static FILE* g_logfile = nullptr;
static char  g_logpath[MAX_PATH] = {};

static void log_init()
{
    HMODULE hSelf = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS, (LPCSTR)&log_init, &hSelf);
    char self_path[MAX_PATH];
    GetModuleFileNameA(hSelf, self_path, MAX_PATH);
    std::string dir(self_path);
    auto pos = dir.rfind('\\');
    if (pos != std::string::npos) dir = dir.substr(0, pos);
    strcpy_s(g_logpath, (dir + "\\toolkit.log").c_str());

    g_logfile = fopen(g_logpath, "w");
    if (g_logfile) {
        fprintf(g_logfile, "[toolkit] Log started %s %s\n", __DATE__, __TIME__);
        fprintf(g_logfile, "[toolkit] Path: %s\n", g_logpath);
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
    SetConsoleTitleA("[Project A] Debug Console v2");

    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    CONSOLE_SCREEN_BUFFER_INFO csbi;
    if (GetConsoleScreenBufferInfo(hOut, &csbi)) {
        COORD size = { csbi.dwSize.X, 9999 };
        SetConsoleScreenBufferSize(hOut, size);
    }

    freopen_s(&g_conout, "CONOUT$", "w", stdout);
    freopen_s(&g_conout, "CONOUT$", "w", stderr);
    SetConsoleOutputCP(CP_UTF8);

    log_msg("[toolkit] ===== Project A Debug Console v2 =====\n");
    log_msg("[toolkit] Build: %s %s\n", __DATE__, __TIME__);
}

// ─── safe memory read ────────────────────────────────────────────────────────
static bool safe_read(const void* addr, void* out, size_t sz)
{
    if (!addr) return false;
    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(addr, &mbi, sizeof(mbi))) return false;
    if (mbi.State != MEM_COMMIT) return false;
    if (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)) return false;
    // Ensure the entire range is within the committed region
    uintptr_t region_end = (uintptr_t)mbi.BaseAddress + mbi.RegionSize;
    if ((uintptr_t)addr + sz > region_end) return false;
    memcpy(out, addr, sz);
    return true;
}

template<typename T>
static bool safe_read_t(const void* addr, T& out)
{
    return safe_read(addr, &out, sizeof(T));
}

// ─── image base ──────────────────────────────────────────────────────────────
static uintptr_t GetImageBase()
{
    return (uintptr_t)GetModuleHandleA(nullptr);
}

static void DumpAresHandlerCode()
{
    static const uint64_t rvas[] = {
        0x02763980, 0x02764930, 0x02764960, 0x02766120,
        0x02766170, 0x02766190, 0x027661D0, 0x02766270,
        0x02766280, 0x027669F0, 0x02766A00, 0x02766B80,
    };

    char out_path[MAX_PATH] = {};
    strcpy_s(out_path, g_logpath);
    char* slash = strrchr(out_path, '\\');
    if (slash) {
        slash[1] = 0;
        strcat_s(out_path, "ares_handler_code_dump.bin");
    } else {
        strcpy_s(out_path, "ares_handler_code_dump.bin");
    }

    FILE* out = fopen(out_path, "wb");
    if (!out) {
        log_msg("[toolkit] AresDump: failed to open %s\n", out_path);
        return;
    }

    uintptr_t base = GetImageBase();
    log_msg("[toolkit] AresDump: base=0x%llX file=%s\n", (unsigned long long)base, out_path);
    for (uint64_t rva : rvas) {
        uint8_t buf[0x400] = {};
        uintptr_t addr = base + (uintptr_t)rva;
        bool ok = safe_read((void*)addr, buf, sizeof(buf));
        fwrite(&rva, sizeof(rva), 1, out);
        uint32_t size = ok ? sizeof(buf) : 0;
        fwrite(&size, sizeof(size), 1, out);
        if (ok) fwrite(buf, 1, sizeof(buf), out);
        log_msg("[toolkit] AresDump: rva=0x%llX addr=0x%llX ok=%d first=%02X %02X %02X %02X\n",
            (unsigned long long)rva, (unsigned long long)addr, ok ? 1 : 0,
            buf[0], buf[1], buf[2], buf[3]);
    }
    fclose(out);
}

static bool PatchRet(uint64_t rva, const char* name)
{
    uint8_t* addr = (uint8_t*)(GetImageBase() + (uintptr_t)rva);
    DWORD old = 0;
    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(addr, &mbi, sizeof(mbi))) {
        log_msg("[toolkit] AresBypass: VirtualQuery failed %s rva=0x%llX err=%lu\n",
            name, (unsigned long long)rva, GetLastError());
        return false;
    }

    if (!VirtualProtect(mbi.BaseAddress, mbi.RegionSize, PAGE_EXECUTE_READWRITE, &old)) {
        log_msg("[toolkit] AresBypass: VirtualProtect failed %s rva=0x%llX addr=%p page=%p size=0x%llX protect=0x%lX state=0x%lX err=%lu\n",
            name, (unsigned long long)rva, addr, mbi.BaseAddress,
            (unsigned long long)mbi.RegionSize, mbi.Protect, mbi.State, GetLastError());
        return false;
    }
    addr[0] = 0xC3;
    for (int i = 1; i < 16; ++i) addr[i] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), addr, 16);
    DWORD ignored = 0;
    VirtualProtect(mbi.BaseAddress, mbi.RegionSize, old, &ignored);
    log_msg("[toolkit] AresBypass: patched %s rva=0x%llX addr=%p\n", name, (unsigned long long)rva, addr);
    return true;
}

static void PatchAresHandlerBypass()
{
    log_msg("[toolkit] AresBypass: patching Ares packet handler transforms\n");
    PatchRet(0x02766170, "AresDispatchA");
    PatchRet(0x02766190, "AresIncomingA");
    PatchRet(0x027661D0, "AresDispatchB");
    PatchRet(0x027669F0, "AresOutgoingGateA");
    PatchRet(0x02766A00, "AresOutgoingA");
    PatchRet(0x02766B80, "AresOutgoingGateB");
}

// ─── FName resolution via AppendString ───────────────────────────────────────
// AppendString: void __fastcall(const FName* this, FString& out)
// FString layout: wchar_t* Data, int32 Count, int32 Max
using AppendString_t = void(__fastcall*)(const void*, void*);

struct FStringBuf {
    wchar_t* Data  = nullptr;
    int32_t  Count = 0;
    int32_t  Max   = 0;
    wchar_t  Inline[512]{};

    FStringBuf() {
        Data  = Inline;
        Max   = 512;
        Count = 0;
        Inline[0] = 0;
    }
};

static std::string ResolveFName(const void* fname_ptr)
{
    // FName layout: int32 ComparisonIndex, int32 DisplayIndex, int32 Number
    FStringBuf buf;
    auto fn = (AppendString_t)(GetImageBase() + OFF_APPENDSTRING);
    fn(fname_ptr, &buf);

    if (!buf.Data || buf.Count <= 0) return "<empty>";

    int len = WideCharToMultiByte(CP_UTF8, 0, buf.Data, buf.Count, nullptr, 0, nullptr, nullptr);
    if (len <= 0) return "<conv-fail>";
    std::string s(len, '\0');
    WideCharToMultiByte(CP_UTF8, 0, buf.Data, buf.Count, &s[0], len, nullptr, nullptr);
    return s;
}

// ─── FGuid formatting ────────────────────────────────────────────────────────
// FGuid: int32 A, B, C, D (CoreUObject_structs.hpp)
// Format matches Riot UUID representation
static std::string FormatGuid(const uint32_t* g)
{
    // A B C D  →  AAAAAAAA-BBBB-BBBB-CCCC-CCCCDDDDDDDD
    char buf[40];
    snprintf(buf, sizeof(buf), "%08x-%04x-%04x-%04x-%04x%08x",
        g[0],
        g[1] >> 16, g[1] & 0xFFFF,
        g[2] >> 16, g[2] & 0xFFFF,
        g[3]);
    return buf;
}

static bool GuidIsZero(const uint32_t* g)
{
    return g[0] == 0 && g[1] == 0 && g[2] == 0 && g[3] == 0;
}

// ─── GObjects (chunked TUObjectArray) ────────────────────────────────────────
// TUObjectArray layout (Basic.hpp):
//   +0x00 FUObjectItem** Objects (chunk table)
//   +0x08 pad
//   +0x10 int32 MaxElements
//   +0x14 int32 NumElements
//   +0x18 int32 MaxChunks
//   +0x1C int32 NumChunks
// FUObjectItem: UObject* Object, uint8 Pad[0x10]  → stride 0x18
// ElementsPerChunk = 0x10000

static constexpr int32_t ELEMENTS_PER_CHUNK = 0x10000;
static constexpr int32_t FOBJECTITEM_STRIDE  = 0x18;

static uintptr_t GetObjectByIndex(int32_t index)
{
    uintptr_t base = GetImageBase();
    uintptr_t gobjs_ptr = base + OFF_GOBJECTS;

    uintptr_t chunk_table = 0;
    int32_t num_elements = 0;
    if (!safe_read_t((void*)gobjs_ptr,         chunk_table))   return 0;
    if (!safe_read_t((void*)(gobjs_ptr + 0x14), num_elements)) return 0;

    if (index < 0 || index >= num_elements) return 0;

    int32_t chunk_idx  = index / ELEMENTS_PER_CHUNK;
    int32_t elem_idx   = index % ELEMENTS_PER_CHUNK;

    uintptr_t chunk_ptr = 0;
    if (!safe_read_t((void*)(chunk_table + (uintptr_t)chunk_idx * 8), chunk_ptr)) return 0;
    if (!chunk_ptr) return 0;

    uintptr_t item_ptr = chunk_ptr + (uintptr_t)elem_idx * FOBJECTITEM_STRIDE;
    uintptr_t obj = 0;
    if (!safe_read_t((void*)item_ptr, obj)) return 0;
    return obj;
}

static int32_t GetNumObjects()
{
    uintptr_t base = GetImageBase();
    int32_t n = 0;
    safe_read_t((void*)(base + OFF_GOBJECTS + 0x14), n);
    return n;
}

// ─── UObject field accessors ─────────────────────────────────────────────────
// UObject layout (CoreUObject_classes.hpp):
//   +0x0000 void* VTable
//   +0x0008 uint32 Flags
//   +0x000C int32  Index
//   +0x0010 UClass* Class
//   +0x0018 FName  Name  (12 bytes: CompIdx, DispIdx, Number)
//   +0x0024 uint8  pad[4]
//   +0x0028 UObject* Outer

static uint32_t ObjFlags(uintptr_t obj)
{
    uint32_t v = 0;
    safe_read_t((void*)(obj + 0x08), v);
    return v;
}

static uintptr_t ObjOuter(uintptr_t obj)
{
    uintptr_t v = 0;
    safe_read_t((void*)(obj + 0x28), v);
    return v;
}

static uintptr_t ObjClass(uintptr_t obj)
{
    uintptr_t v = 0;
    safe_read_t((void*)(obj + 0x10), v);
    return v;
}

static std::string ObjName(uintptr_t obj)
{
    return ResolveFName((void*)(obj + 0x18));
}

static std::string ClassName(uintptr_t obj)
{
    uintptr_t cls = ObjClass(obj);
    if (!cls) return "<no-class>";
    return ResolveFName((void*)(cls + 0x18));
}

static bool IsCDOOrArchetype(uintptr_t obj);

struct FFString {
    wchar_t* Data;
    int32_t  Count;
    int32_t  Max;
};

struct FTArray {
    uintptr_t Data;
    int32_t Count;
    int32_t Max;
};

using ProcessEvent_t = void(__fastcall*)(uintptr_t obj, uintptr_t func, void* parms);

struct RepairRangeSpawnArgs {
    uintptr_t initialController;
};

static const uint32_t PHOENIX_GUID[4] = {
    0xEB93336A,
    0x449B9C1B,
    0x0A54A891,
    0xF7921D69,
};

static std::string OuterChain(uintptr_t obj, int maxDepth = 6)
{
    std::string out;
    uintptr_t cur = ObjOuter(obj);
    for (int i = 0; cur && i < maxDepth; ++i) {
        std::string name = ObjName(cur);
        if (name.empty()) name = "<empty>";
        if (!out.empty()) out += " <- ";
        out += name;
        cur = ObjOuter(cur);
    }
    return out.empty() ? "<none>" : out;
}

static bool IsLiveObject(uintptr_t obj)
{
    if (!obj) return false;
    if (IsCDOOrArchetype(obj)) return false;
    if (!ObjClass(obj)) return false;
    std::string cn = ClassName(obj);
    return !cn.empty() && cn != "<no-class>";
}

static bool IsGameplayControllerClassName(const std::string& cn)
{
    return
        cn.find("ShooterPlayerController") != std::string::npos ||
        cn.find("ShootingRangeController") != std::string::npos ||
        cn.find("ObserverPlayerController") != std::string::npos ||
        cn.find("PregamePlayerController") != std::string::npos ||
        cn.find("AresPlayerController") != std::string::npos ||
        cn.find("MainMenuPlayerController") != std::string::npos ||
        cn.find("PlayerController") != std::string::npos;
}

static int ScoreControllerCandidate(uintptr_t obj)
{
    if (!IsLiveObject(obj)) return -1000000;

    std::string cn = ClassName(obj);
    std::string name = ObjName(obj);
    std::string outers = OuterChain(obj);
    int score = 0;

    if (cn.find("ShooterPlayerController") != std::string::npos) score += 1000;
    else if (cn.find("ShootingRangeController") != std::string::npos) score += 950;
    else if (cn.find("ObserverPlayerController") != std::string::npos) score += 700;
    else if (cn.find("PregamePlayerController") != std::string::npos) score += 450;
    else if (cn.find("AresPlayerController") != std::string::npos) score += 350;
    else if (cn.find("PlayerController") != std::string::npos) score += 200;
    else return -1000000;

    if (cn.find("MainMenu") != std::string::npos) score -= 500;
    if (name.find("MainMenu") != std::string::npos) score -= 500;
    if (outers.find("Range") != std::string::npos) score += 250;
    if (outers.find("Poveglia") != std::string::npos) score += 250;
    if (outers.find("PersistentLevel") != std::string::npos) score += 100;
    if (outers.find("MainMenu") != std::string::npos) score -= 400;

    uint8_t role = 0;
    safe_read_t((void*)(obj + 0x01F4), role);
    if (role >= 2) score += 50;

    return score;
}

static ProcessEvent_t GetProcessEvent()
{
    return (ProcessEvent_t)(GetImageBase() + OFF_PROCESSEVENT);
}

static uintptr_t FindEngineObject()
{
    int32_t n = GetNumObjects();
    for (int32_t i = 0; i < n; ++i) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj || IsCDOOrArchetype(obj)) continue;
        std::string cn = ClassName(obj);
        std::string name = ObjName(obj);
        if (cn.find("GameEngine") != std::string::npos ||
            cn == "Engine" ||
            name.find("GameEngine") != std::string::npos) {
            return obj;
        }
    }
    return 0;
}

static void DumpNetDriverObject(uintptr_t obj, const char* prefix)
{
    if (!obj) return;

    uintptr_t serverConnection = 0;
    uintptr_t world = 0;
    uintptr_t replicationDriver = 0;
    safe_read_t((void*)(obj + 0x0098), serverConnection);
    safe_read_t((void*)(obj + 0x0150), world);
    safe_read_t((void*)(obj + 0x0710), replicationDriver);

    log_msg("[toolkit]   %s NetDriver=0x%llX Class=%s Name=%s NetDriverName=%s ServerConnection=0x%llX World=0x%llX ReplicationDriver=0x%llX\n",
        prefix ? prefix : "Object",
        (unsigned long long)obj,
        ClassName(obj).c_str(),
        ObjName(obj).c_str(),
        ResolveFName((void*)(obj + 0x01A0)).c_str(),
        (unsigned long long)serverConnection,
        (unsigned long long)world,
        (unsigned long long)replicationDriver);

    if (serverConnection) {
        uintptr_t driverFromConnection = 0;
        safe_read_t((void*)(serverConnection + 0x0060), driverFromConnection);
        log_msg("[toolkit]     ServerConnection Class=%s Name=%s Driver=0x%llX\n",
            ClassName(serverConnection).c_str(),
            ObjName(serverConnection).c_str(),
            (unsigned long long)driverFromConnection);
    }
}

static void DumpNetObjectInventory()
{
    int32_t n = GetNumObjects();
    int engineCandidates = 0;
    int pendingNetGames = 0;
    int netDrivers = 0;

    for (int32_t i = 0; i < n; ++i) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj || IsCDOOrArchetype(obj) || !ObjClass(obj)) continue;

        std::string cn = ClassName(obj);
        std::string name = ObjName(obj);

        if ((cn.find("GameEngine") != std::string::npos || cn == "Engine" || name.find("GameEngine") != std::string::npos) &&
            engineCandidates < 8) {
            ++engineCandidates;
            log_msg("[toolkit]   EngineCandidate[%d] Obj=0x%llX Class=%s Name=%s Outer=%s\n",
                engineCandidates,
                (unsigned long long)obj,
                cn.c_str(),
                name.c_str(),
                OuterChain(obj).c_str());
        }

        if (cn.find("PendingNetGame") != std::string::npos && pendingNetGames < 8) {
            ++pendingNetGames;
            uintptr_t pendingDriver = 0;
            uintptr_t demoDriver = 0;
            safe_read_t((void*)(obj + 0x0038), pendingDriver);
            safe_read_t((void*)(obj + 0x0040), demoDriver);
            log_msg("[toolkit]   PendingNetGame[%d] Obj=0x%llX Class=%s Name=%s NetDriver=0x%llX DemoNetDriver=0x%llX Outer=%s\n",
                pendingNetGames,
                (unsigned long long)obj,
                cn.c_str(),
                name.c_str(),
                (unsigned long long)pendingDriver,
                (unsigned long long)demoDriver,
                OuterChain(obj).c_str());
            if (pendingDriver) DumpNetDriverObject(pendingDriver, "PendingNetGame");
        }

        if (cn.find("NetDriver") != std::string::npos && netDrivers < 12) {
            ++netDrivers;
            DumpNetDriverObject(obj, "Live");
        }
    }

    log_msg("[toolkit]   Inventory totals shown: EngineCandidates=%d PendingNetGames=%d NetDrivers=%d\n",
        engineCandidates, pendingNetGames, netDrivers);
}

static void DumpNetworkRuntimeState(const char* reason)
{
    uintptr_t world = 0;
    safe_read_t((void*)(GetImageBase() + OFF_GWORLD), world);

    log_msg("[toolkit] NetState[%s]\n", reason ? reason : "unknown");
    if (world) {
        uintptr_t netDriver = 0;
        uintptr_t authGameMode = 0;
        uintptr_t persistentLevel = 0;
        safe_read_t((void*)(world + 0x0040), netDriver);
        safe_read_t((void*)(world + 0x0138), authGameMode);
        safe_read_t((void*)(world + 0x0038), persistentLevel);
        log_msg("[toolkit]   World=0x%llX Name=%s PersistentLevel=0x%llX NetDriver=0x%llX AuthorityGameMode=0x%llX",
            (unsigned long long)world,
            ObjName(world).c_str(),
            (unsigned long long)persistentLevel,
            (unsigned long long)netDriver,
            (unsigned long long)authGameMode);
        if (authGameMode) {
            log_msg(" GMClass=%s GMName=%s", ClassName(authGameMode).c_str(), ObjName(authGameMode).c_str());
        }
        log_msg("\n");
    } else {
        log_msg("[toolkit]   World=null\n");
    }

    uintptr_t engine = FindEngineObject();
    if (!engine) {
        log_msg("[toolkit]   Engine object not found\n");
        DumpNetObjectInventory();
        return;
    }

    FTArray defs{};
    safe_read((void*)(engine + 0x0CF8), &defs, sizeof(defs));
    log_msg("[toolkit]   Engine=0x%llX Class=%s Name=%s NetDriverDefinitions Data=0x%llX Count=%d Max=%d\n",
        (unsigned long long)engine,
        ClassName(engine).c_str(),
        ObjName(engine).c_str(),
        (unsigned long long)defs.Data,
        defs.Count,
        defs.Max);

    if (!defs.Data || defs.Count <= 0 || defs.Count > 16) return;
    for (int32_t i = 0; i < defs.Count; ++i) {
        uintptr_t entry = defs.Data + (uintptr_t)i * 0x24;
        log_msg("[toolkit]     Def[%d] DefName=%s Driver=%s Fallback=%s\n",
            i,
            ResolveFName((void*)(entry + 0x00)).c_str(),
            ResolveFName((void*)(entry + 0x0C)).c_str(),
            ResolveFName((void*)(entry + 0x18)).c_str());
    }

    DumpNetObjectInventory();
}

static uintptr_t FindBestPlayerController(bool logCandidates, const char* classNeedle = nullptr)
{
    int32_t n = GetNumObjects();
    uintptr_t best = 0;
    int bestScore = -1000000;
    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (!IsLiveObject(obj)) continue;
        std::string cn = ClassName(obj);
        if (!IsGameplayControllerClassName(cn)) continue;
        if (classNeedle && cn.find(classNeedle) == std::string::npos) continue;

        uint8_t role = 0;
        safe_read_t((void*)(obj + 0x01F4), role);
        int score = ScoreControllerCandidate(obj);
        if (logCandidates) {
            log_msg("[toolkit] PC seen: 0x%llX Class=%s Name=%s Role=%d Score=%d Outer=%s\n",
                (unsigned long long)obj, cn.c_str(), ObjName(obj).c_str(), (int)role, score, OuterChain(obj).c_str());
        }
        if (score > bestScore) {
            best = obj;
            bestScore = score;
        }
    }
    return best;
}

static bool ClassLooksInterestingForRangeCensus(const std::string& cn)
{
    static const char* needles[] = {
        "Controller",
        "GameMode",
        "GameState",
        "PlayerState",
        "TeamComponent",
        "Pawn",
        "Character",
        "RespawnManager",
        "PlayerSpawner",
        "Spawn",
        "DataAsset",
        "PrimaryAsset",
        "Megapacket",
    };
    for (const char* needle : needles) {
        if (cn.find(needle) != std::string::npos) return true;
    }
    return false;
}

static void DumpRangeWorldCensus(const char* reason, int maxLines = 160)
{
    log_msg("\n[toolkit] ===== Range Census (%s) =====\n", reason ? reason : "unknown");
    uintptr_t world = 0;
    safe_read_t((void*)(GetImageBase() + OFF_GWORLD), world);
    log_msg("[toolkit] GWorld=0x%llX Name=%s\n",
        (unsigned long long)world,
        world ? ObjName(world).c_str() : "<null>");

    int32_t n = GetNumObjects();
    int shown = 0;
    for (int32_t i = 0; i < n && shown < maxLines; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (!IsLiveObject(obj)) continue;

        std::string cn = ClassName(obj);
        if (!ClassLooksInterestingForRangeCensus(cn)) continue;

        std::string name = ObjName(obj);
        std::string outer = OuterChain(obj);
        if (
            outer.find("Range") == std::string::npos &&
            outer.find("Poveglia") == std::string::npos &&
            name.find("Range") == std::string::npos &&
            cn.find("PlayerController") == std::string::npos &&
            cn.find("PlayerState") == std::string::npos &&
            cn.find("TeamComponent") == std::string::npos
        ) {
            continue;
        }

        uint8_t role = 0;
        safe_read_t((void*)(obj + 0x01F4), role);
        log_msg("[toolkit] Census: 0x%llX Class=%s Name=%s Role=%d Outer=%s\n",
            (unsigned long long)obj, cn.c_str(), name.c_str(), (int)role, outer.c_str());
        shown++;
    }
    if (!shown) {
        log_msg("[toolkit] Census found no live interesting objects\n");
    }
    log_msg("[toolkit] ===== End Range Census =====\n\n");
}

static void DumpGameModeSpawnState()
{
    int32_t n = GetNumObjects();
    uintptr_t gm = 0;
    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;
        std::string cn = ClassName(obj);
        if (cn.find("ShootingRangeGameMode") == std::string::npos) continue;
        gm = obj;
        break;
    }
    if (!gm) {
        log_msg("[toolkit] No ShootingRangeGameMode found in census\n");
        return;
    }
    log_msg("[toolkit] GameMode: 0x%llX Class=%s Name=%s\n",
        (unsigned long long)gm, ClassName(gm).c_str(), ObjName(gm).c_str());

    struct TArrayPtr { void* Data; int32_t Count; int32_t Max; };
    TArrayPtr playersToSpawn{};
    TArrayPtr spawnTimes{};
    float respawnDelay = 0.0f;
    safe_read((void*)(gm + 0x838), &playersToSpawn, sizeof(playersToSpawn));
    safe_read((void*)(gm + 0x848), &spawnTimes, sizeof(spawnTimes));
    safe_read((void*)(gm + 0x858), &respawnDelay, sizeof(respawnDelay));

    log_msg("[toolkit] PlayersToSpawn: count=%d  SpawnTimes: count=%d  RespawnDelay=%.2f\n",
        playersToSpawn.Count, spawnTimes.Count, respawnDelay);

    uintptr_t localPC = FindBestPlayerController(false, nullptr);
    uintptr_t localPS = 0;
    if (localPC) {
        safe_read_t((void*)(localPC + 0x0498), localPS);
    }
    log_msg("[toolkit] Local PC=0x%llX  Local PS=0x%llX\n",
        (unsigned long long)localPC, (unsigned long long)localPS);

    bool inQueue = false;
    if (playersToSpawn.Data && playersToSpawn.Count > 0 && localPS) {
        for (int i = 0; i < playersToSpawn.Count && i < 32; i++) {
            uintptr_t ps = 0;
            safe_read_t((void*)((uintptr_t)playersToSpawn.Data + i * sizeof(void*)), ps);
            std::string psName = ps ? ObjName(ps) : "<null>";
            std::string psClass = ps ? ClassName(ps) : "<null>";
            bool isLocal = (ps == localPS);
            if (isLocal) inQueue = true;
            log_msg("[toolkit] PlayersToSpawn[%d]: 0x%llX Class=%s Name=%s %s\n",
                i, (unsigned long long)ps, psClass.c_str(), psName.c_str(), isLocal ? "<-- LOCAL" : "");
        }
    }
    if (!inQueue && localPS) {
        log_msg("[toolkit] WARNING: Local PlayerState is NOT in PlayersToSpawn queue\n");
    } else if (inQueue) {
        log_msg("[toolkit] Local PlayerState IS in PlayersToSpawn queue (spawn pending)\n");
    }
}

static void DumpManualRangeCensus()
{
    DumpRangeWorldCensus("manual-hotkey-f8", 260);
    uintptr_t best = FindBestPlayerController(true, nullptr);
    if (best) {
        log_msg("[toolkit] Best controller candidate: 0x%llX Class=%s Name=%s Outer=%s\n",
            (unsigned long long)best, ClassName(best).c_str(), ObjName(best).c_str(), OuterChain(best).c_str());
    } else {
        log_msg("[toolkit] No gameplay controller candidate found by manual census\n");
    }
    DumpGameModeSpawnState();
}

static FFString MakeTempFString(const wchar_t* text, wchar_t** allocation)
{
    int len = (int)wcslen(text);
    wchar_t* buf = (wchar_t*)malloc((len + 1) * sizeof(wchar_t));
    memcpy(buf, text, (len + 1) * sizeof(wchar_t));
    *allocation = buf;
    FFString fs{};
    fs.Data = buf;
    fs.Count = len;
    fs.Max = len + 1;
    return fs;
}

static bool IsCDOOrArchetype(uintptr_t obj)
{
    uint32_t f = ObjFlags(obj);
    return (f & RF_ClassDefaultObject) || (f & RF_ArchetypeObject);
}

// ─── Dump functions ───────────────────────────────────────────────────────────

static void DumpStats()
{
    log_msg("\n========== [F1] STATS ==========\n");
    uintptr_t base = GetImageBase();
    log_msg("ImageBase:   0x%llX\n", (unsigned long long)base);
    log_msg("GObjects:    0x%llX\n", (unsigned long long)(base + OFF_GOBJECTS));
    log_msg("AppendStr:   0x%llX\n", (unsigned long long)(base + OFF_APPENDSTRING));
    log_msg("GWorld:      0x%llX\n", (unsigned long long)(base + OFF_GWORLD));

    int32_t n = GetNumObjects();
    log_msg("NumObjects:  %d\n", n);

    // GWorld name
    uintptr_t world = 0;
    safe_read_t((void*)(base + OFF_GWORLD), world);
    if (world) {
        log_msg("GWorld:      0x%llX  Name=%s\n", (unsigned long long)world, ObjName(world).c_str());
    } else {
        log_msg("GWorld:      null\n");
    }
    log_msg("=================================\n\n");
}

// F2: character data assets
static void DumpCharacterAssets()
{
    log_msg("\n========== [F2] CHARACTER ASSETS ==========\n");
    int32_t n = GetNumObjects();
    int count = 0;

    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;

        std::string cn = ClassName(obj);
        bool isCharAsset  = (cn.find("CharacterDataAsset") != std::string::npos);
        bool isBPAsset    = (cn.find("BaseCharacterPrimaryDataAsset") != std::string::npos);
        if (!isCharAsset && !isBPAsset) continue;

        std::string name = ObjName(obj);

        // Uuid @ 0x38 (UAresBasePrimaryDataAsset::Uuid, FGuid 16 bytes)
        uint32_t guid[4] = {};
        bool has_uuid = safe_read((void*)(obj + 0x38), guid, 16);
        std::string uuid_str = has_uuid ? FormatGuid(guid) : "<no-uuid>";

        // DeveloperName FName @ 0x110 (UCharacterDataAsset)
        std::string devname = "<n/a>";
        if (obj + 0x110 > obj) {
            devname = ResolveFName((void*)(obj + 0x110));
        }

        // bIsPlayableCharacter @ 0x011C
        uint8_t playable = 0;
        safe_read_t((void*)(obj + 0x011C), playable);

        // ECharacterID @ 0x120 (only for BP subclass)
        std::string char_id_str = "";
        if (isBPAsset) {
            uint8_t cid = 0;
            safe_read_t((void*)(obj + 0x120), cid);
            char_id_str = std::string(" CharID=") + CharacterIDName(cid) + "(" + std::to_string(cid) + ")";
        }

        log_msg("[%04d] [%s] %s\n      UUID=%s  Dev=%s  Playable=%d%s\n",
            count++, cn.c_str(), name.c_str(),
            uuid_str.c_str(), devname.c_str(), playable, char_id_str.c_str());
    }

    if (count == 0)
        log_msg("  (none found — try after level load)\n");
    log_msg("===========================================\n\n");
}

// F3: equippable skin assets
static void DumpSkinAssets()
{
    log_msg("\n========== [F3] SKIN/EQUIPPABLE ASSETS ==========\n");
    int32_t n = GetNumObjects();
    int count = 0;

    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;

        std::string cn = ClassName(obj);
        // must be a DataAsset, not a HUD element or anim notify
        if (cn.find("DataAsset") == std::string::npos) continue;
        if (cn.find("Equippable") == std::string::npos &&
            cn.find("Skin") == std::string::npos &&
            cn.find("Chroma") == std::string::npos &&
            cn.find("WeaponSkin") == std::string::npos) continue;

        std::string name = ObjName(obj);

        // UUID @ 0x38
        uint32_t guid[4] = {};
        bool has_uuid = safe_read((void*)(obj + 0x38), guid, 16);
        if (!has_uuid || GuidIsZero(guid)) continue;

        log_msg("[%04d] [%s] %s\n      UUID=%s\n",
            count++, cn.c_str(), name.c_str(), FormatGuid(guid).c_str());
    }

    if (count == 0)
        log_msg("  (none found)\n");
    log_msg("=================================================\n\n");
}

// F4: all primary data assets (anything with a non-zero UUID @ 0x38 and DataAsset/PrimaryAsset in class name)
static void DumpAllDataAssets()
{
    log_msg("\n========== [F4] ALL DATA ASSETS ==========\n");
    int32_t n = GetNumObjects();
    int count = 0;

    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;

        std::string cn = ClassName(obj);
        if (cn.find("DataAsset") == std::string::npos &&
            cn.find("PrimaryAsset") == std::string::npos) continue;

        uint32_t guid[4] = {};
        if (!safe_read((void*)(obj + 0x38), guid, 16)) continue;
        if (GuidIsZero(guid)) continue;

        std::string name = ObjName(obj);
        log_msg("[%04d] [%s] %s  UUID=%s\n",
            count++, cn.c_str(), name.c_str(), FormatGuid(guid).c_str());
    }

    if (count == 0)
        log_msg("  (none found)\n");
    log_msg("==========================================\n\n");
}

// F5: brute-force all non-CDO objects that have a non-zero FGuid @ +0x38
static void DumpAllUUIDs()
{
    log_msg("\n========== [F5] ALL OBJECTS WITH UUID @ 0x38 ==========\n");
    int32_t n = GetNumObjects();
    int count = 0;

    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;

        uint32_t guid[4] = {};
        if (!safe_read((void*)(obj + 0x38), guid, 16)) continue;
        if (GuidIsZero(guid)) continue;

        std::string name = ObjName(obj);
        std::string cn   = ClassName(obj);
        log_msg("[%05d] [%s] %s  UUID=%s\n",
            count++, cn.c_str(), name.c_str(), FormatGuid(guid).c_str());
    }

    log_msg("Total: %d objects with UUID\n", count);
    log_msg("========================================================\n\n");
}

// F6: dump all unique class names present in GObjects (diagnostic)
static void DumpClassNames()
{
    log_msg("\n========== [F6] CLASS NAME CENSUS ==========\n");
    int32_t n = GetNumObjects();
    std::map<std::string, int> counts;

    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        counts[ClassName(obj)]++;
    }

    // print sorted by count descending
    std::vector<std::pair<int,std::string>> sorted;
    sorted.reserve(counts.size());
    for (auto& kv : counts) sorted.push_back({kv.second, kv.first});
    std::sort(sorted.begin(), sorted.end(), [](auto& a, auto& b){ return a.first > b.first; });

    int shown = 0;
    for (auto& p : sorted) {
        log_msg("  %5d  %s\n", p.first, p.second.c_str());
        if (++shown >= 200) { log_msg("  ... (truncated)\n"); break; }
    }
    log_msg("Total unique classes: %zu\n", counts.size());
    log_msg("=============================================\n\n");
}

// ─── hotkey thread ────────────────────────────────────────────────────────────
static uintptr_t FindFunctionByName(const char* className, const char* funcName)
{
    int32_t n = GetNumObjects();
    int foundCount = 0;
    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        std::string cn = ClassName(obj);
        if (cn.find("Function") == std::string::npos) continue;
        std::string name = ObjName(obj);
        if (name.find(funcName) == std::string::npos) continue;
        uintptr_t outer = 0;
        safe_read_t((void*)(obj + 0x28), outer);
        if (!outer) continue;
        std::string outerName = ObjName(outer);
        if (outerName.find(className) != std::string::npos) {
            log_msg("[toolkit] Found func: %s in class %s (outer=%s) @ 0x%llX\n",
                name.c_str(), cn.c_str(), outerName.c_str(), (unsigned long long)obj);
            return obj;
        }
        if (++foundCount < 10) {
            log_msg("[toolkit] Candidate: func=%s class=%s outer=%s\n",
                name.c_str(), cn.c_str(), outerName.c_str());
        }
    }
    log_msg("[toolkit] FindFunctionByName: scanned %d objects, found %d candidates, no match for %s in %s\n",
        n, foundCount, funcName, className);
    return 0;
}

static DWORD WINAPI RepairRangeSpawnThread(LPVOID rawArgs)
{
    RepairRangeSpawnArgs* args = (RepairRangeSpawnArgs*)rawArgs;
    log_msg("[toolkit] RepairRangeSpawnThread started\n");

    uintptr_t setTeamFunc = 0;
    uintptr_t respawnFunc = 0;
    uintptr_t possessFunc = 0;
    uintptr_t serverConsoleCommandFunc = 0;
    uintptr_t toggleObserverFreeCamFunc = 0;
    uintptr_t getAresPlayerStateFunc = 0;
    uintptr_t getTeamComponentFunc = 0;
    uintptr_t authSetDesiredClassFunc = 0;
    uintptr_t bombAuthSetTeamFunc = 0;
    uintptr_t serverSetDesiredClassFunc = 0;
    uintptr_t serverSetDesiredClassAndRespawnFunc = 0;
    bool loggedCandidates = false;

    for (int attempt = 0; attempt < 120; ++attempt) {
        Sleep(250);

        uintptr_t world = 0;
        safe_read_t((void*)(GetImageBase() + OFF_GWORLD), world);
        std::string worldName = world ? ObjName(world) : "<null>";
        bool inRangeWorld = worldName.find("Range") != std::string::npos;

        if (!inRangeWorld) {
            if ((attempt % 8) == 0) {
                log_msg("[toolkit] Waiting for Range world before controller repair... GWorld=%s\n", worldName.c_str());
            }
            continue;
        }

        uintptr_t shooterPC = FindBestPlayerController(attempt >= 4 && !loggedCandidates, "ShooterPlayerController");
        if (!shooterPC) shooterPC = FindBestPlayerController(false, "ShootingRangeController");
        uintptr_t observerPC = FindBestPlayerController(false, "ObserverPlayerController");
        uintptr_t localPC = shooterPC ? shooterPC : (observerPC ? observerPC : FindBestPlayerController(attempt >= 4 && !loggedCandidates));
        if (attempt >= 4 && !loggedCandidates) {
            loggedCandidates = true;
        }
        if (!localPC) {
            if ((attempt % 8) == 0) {
                log_msg("[toolkit] Waiting for local PlayerController... GWorld=%s\n", worldName.c_str());
            }
            if (attempt == 16 || attempt == 40 || attempt == 80) {
                DumpRangeWorldCensus("waiting-for-playercontroller");
            }
            continue;
        }

        std::string localClass = ClassName(localPC);
        log_msg("[toolkit] Found local controller: 0x%llX Class=%s Name=%s World=%s Outer=%s\n",
            (unsigned long long)localPC, localClass.c_str(), ObjName(localPC).c_str(), worldName.c_str(), OuterChain(localPC).c_str());

        if (!setTeamFunc) setTeamFunc = FindFunctionByName("ShooterPlayerController", "ServerSetTeam");
        if (!respawnFunc) respawnFunc = FindFunctionByName("ShooterPlayerController", "Respawn");
        if (!possessFunc) possessFunc = FindFunctionByName("ShooterPlayerController", "AuthPossessSpawnedCharacter");
        if (!serverConsoleCommandFunc) serverConsoleCommandFunc = FindFunctionByName("AresPlayerController", "ServerConsoleCommand");
        if (!toggleObserverFreeCamFunc) toggleObserverFreeCamFunc = FindFunctionByName("ObserverPlayerController", "RequestToggleObserverFreeCam");
        if (!getAresPlayerStateFunc) getAresPlayerStateFunc = FindFunctionByName("AresPlayerController", "GetAresPlayerState");
        if (!getTeamComponentFunc) getTeamComponentFunc = FindFunctionByName("AresPlayerStateBase", "GetTeamComponent");
        if (!authSetDesiredClassFunc) authSetDesiredClassFunc = FindFunctionByName("ShooterPlayerState", "AuthSetDesiredClass");
        if (!bombAuthSetTeamFunc) bombAuthSetTeamFunc = FindFunctionByName("BombTeamComponent", "AuthSetTeam");
        if (!serverSetDesiredClassFunc) serverSetDesiredClassFunc = FindFunctionByName("ShooterPlayerController", "ServerSetDesiredClass");
        if (!serverSetDesiredClassAndRespawnFunc) serverSetDesiredClassAndRespawnFunc = FindFunctionByName("ShooterPlayerController", "ServerSetDesiredClassAndRespawn");

        auto pe = GetProcessEvent();
        if (!pe) {
            log_msg("[toolkit] ProcessEvent missing\n");
            return 0;
        }

        bool canUseShooterFuncs =
            shooterPC &&
            (
                localClass.find("ShooterPlayerController") != std::string::npos ||
                localClass.find("ShootingRangeController") != std::string::npos
            );
        bool canUseServerConsole =
            localClass.find("PlayerController") != std::string::npos ||
            localClass.find("ShootingRangeController") != std::string::npos ||
            localClass.find("AresPlayerController") != std::string::npos;

        if (canUseShooterFuncs && serverSetDesiredClassAndRespawnFunc) {
            struct ServerSetDesiredClassAndRespawnParams {
                FFString NewDesiredClass;
            } params{};
            wchar_t* desiredBuf = nullptr;
            params.NewDesiredClass = MakeTempFString(L"Phoenix", &desiredBuf);
            log_msg("[toolkit] Calling ServerSetDesiredClassAndRespawn(Phoenix)\n");
            pe(shooterPC, serverSetDesiredClassAndRespawnFunc, &params);
            free(desiredBuf);
        } else if (canUseShooterFuncs && serverSetDesiredClassFunc) {
            struct ServerSetDesiredClassParams {
                FFString NewDesiredClass;
            } params{};
            wchar_t* desiredBuf = nullptr;
            params.NewDesiredClass = MakeTempFString(L"Phoenix", &desiredBuf);
            log_msg("[toolkit] Calling ServerSetDesiredClass(Phoenix)\n");
            pe(shooterPC, serverSetDesiredClassFunc, &params);
            free(desiredBuf);
        }

        if (canUseShooterFuncs && setTeamFunc) {
            struct ServerSetTeamParams {
                FFString TeamName;
            } params{};
            wchar_t* teamBuf = nullptr;
            params.TeamName = MakeTempFString(L"Blue", &teamBuf);
            log_msg("[toolkit] Calling ServerSetTeam(Blue)\n");
            pe(shooterPC, setTeamFunc, &params);
            free(teamBuf);
        } else {
            log_msg("[toolkit] Shooter ServerSetTeam path unavailable on class=%s\n", localClass.c_str());
        }

        Sleep(200);

        if (canUseShooterFuncs && respawnFunc) {
            log_msg("[toolkit] Calling Respawn()\n");
            pe(shooterPC, respawnFunc, nullptr);
        } else {
            log_msg("[toolkit] Shooter Respawn path unavailable on class=%s\n", localClass.c_str());
        }

        Sleep(200);

        if (canUseShooterFuncs && possessFunc) {
            log_msg("[toolkit] Calling AuthPossessSpawnedCharacter()\n");
            pe(shooterPC, possessFunc, nullptr);
        } else {
            log_msg("[toolkit] Shooter AuthPossessSpawnedCharacter path unavailable on class=%s\n", localClass.c_str());
        }

        if (serverConsoleCommandFunc && canUseServerConsole) {
            struct ServerConsoleCommandParams {
                FFString Text;
            } params{};
            wchar_t* cmdBuf = nullptr;
            params.Text = MakeTempFString(L"setteam Blue", &cmdBuf);
            log_msg("[toolkit] Calling ServerConsoleCommand(setteam Blue)\n");
            pe(localPC, serverConsoleCommandFunc, &params);
            free(cmdBuf);

            Sleep(150);

            cmdBuf = nullptr;
            params.Text = MakeTempFString(L"respawn", &cmdBuf);
            log_msg("[toolkit] Calling ServerConsoleCommand(respawn)\n");
            pe(localPC, serverConsoleCommandFunc, &params);
            free(cmdBuf);
        } else {
            log_msg("[toolkit] ServerConsoleCommand unavailable on class=%s\n", localClass.c_str());
        }

        if (localClass.find("ObserverPlayerController") != std::string::npos && toggleObserverFreeCamFunc) {
            Sleep(150);
            log_msg("[toolkit] Calling RequestToggleObserverFreeCam()\n");
            pe(localPC, toggleObserverFreeCamFunc, nullptr);
        }

        log_msg("[toolkit] RepairRangeSpawnThread finished\n");
        if (args) free(args);
        return 0;
    }

    DumpRangeWorldCensus("repair-thread-timeout");
    log_msg("[toolkit] RepairRangeSpawnThread timed out waiting for ShooterPlayerController\n");
    if (args) free(args);
    return 0;
}

// ─── Force local map travel (F7) ────────────────────────────────────────────
static void ForceLocalTravel()
{
    log_msg("[toolkit] ForceLocalTravel called\n");

    // Get GWorld
    uintptr_t base = GetImageBase();
    uintptr_t world = 0;
    safe_read_t((void*)(base + OFF_GWORLD), world);
    if (!world) {
        log_msg("[toolkit] GWorld is null\n");
        return;
    }
    log_msg("[toolkit] GWorld = 0x%llX  Name=%s\n", world, ObjName(world).c_str());
    bool alreadyInRange = ObjName(world).find("Range") != std::string::npos;

    // Find ClientTravel UFunction
    uintptr_t clientTravelFunc = FindFunctionByName("PlayerController", "ClientTravel");
    if (!clientTravelFunc) {
        log_msg("[toolkit] ClientTravel UFunction not found\n");
        return;
    }
    log_msg("[toolkit] ClientTravel UFunction = 0x%llX\n", clientTravelFunc);

    int32_t n = GetNumObjects();
    uintptr_t localPC = 0;
    for (int32_t i = 0; i < n; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj) continue;
        if (IsCDOOrArchetype(obj)) continue;
        std::string cn = ClassName(obj);
        if (!IsGameplayControllerClassName(cn)) continue;
        uint8_t role = 0;
        safe_read_t((void*)(obj + 0x01F4), role);
        log_msg("[toolkit] PC candidate: 0x%llX Class=%s Name=%s Role=%d\n",
            (unsigned long long)obj, cn.c_str(), ObjName(obj).c_str(), (int)role);
        if (role >= 2) {
            localPC = obj;
            break;
        }
    }
    if (!localPC) {
        log_msg("[toolkit] No local PlayerController instance found (all were CDOs or missing)\n");
        DumpRangeWorldCensus("force-local-travel-no-playercontroller");
        return;
    }
    log_msg("[toolkit] Local PC = 0x%llX  Name=%s\n", (unsigned long long)localPC, ObjName(localPC).c_str());

    // Use LocalTravel instead of ClientTravel - it's designed for local/solo play
    uintptr_t localTravelFunc = FindFunctionByName("PlayerController", "LocalTravel");
    if (!localTravelFunc) {
        log_msg("[toolkit] LocalTravel UFunction not found, falling back to ClientTravel\n");
        localTravelFunc = clientTravelFunc;
    }

    // Use the full game mode asset path and explicitly skip spectator bootstrap.
    // Unreal URL options in this build are chained with additional '?' segments.
    const wchar_t* urlW =
        L"/Game/Maps/Poveglia/Range"
        L"?game=/Game/GameModes/ShootingRange/ShootingRangeGameMode.ShootingRangeGameMode_C"
        L"?SkipSpawnSpectatorController=1";
    wchar_t* buf = nullptr;
    FFString fs = MakeTempFString(urlW, &buf);

    if (alreadyInRange) {
        log_msg("[toolkit] Already in Range world, skipping LocalTravel\n");
        if (!ENABLE_RANGE_CONTROLLER_REPAIR) {
            log_msg("[toolkit] Controller repair disabled; using API-driven solo Range flow\n");
            return;
        }
        RepairRangeSpawnArgs* repairArgs = (RepairRangeSpawnArgs*)malloc(sizeof(RepairRangeSpawnArgs));
        if (repairArgs) {
            memset(repairArgs, 0, sizeof(*repairArgs));
            repairArgs->initialController = localPC;
            CreateThread(nullptr, 0, RepairRangeSpawnThread, repairArgs, 0, nullptr);
        }
        return;
    }

    if (localTravelFunc == clientTravelFunc) {
        struct ClientTravelParams {
            FFString   URL;
            uint8_t    TravelType;
            uint8_t    bSeamless;
            uint8_t    pad[2];
            uint32_t   Guid[4];
        } params = {};
        params.URL        = fs;
        params.TravelType = 0;
        params.bSeamless  = false;
        auto pe = GetProcessEvent();
        log_msg("[toolkit] Calling ClientTravel(%S)\n", urlW);
        pe(localPC, clientTravelFunc, &params);
    } else {
        struct LocalTravelParams {
            FFString URL;
        } params = {};
        params.URL = fs;
        auto pe = GetProcessEvent();
        log_msg("[toolkit] Calling LocalTravel(%S)\n", urlW);
        pe(localPC, localTravelFunc, &params);
    }

    free(buf);
    log_msg("[toolkit] Travel call dispatched\n");
    if (!ENABLE_RANGE_CONTROLLER_REPAIR) {
        log_msg("[toolkit] Controller repair disabled; using API-driven solo Range flow\n");
        return;
    }
    RepairRangeSpawnArgs* repairArgs = (RepairRangeSpawnArgs*)malloc(sizeof(RepairRangeSpawnArgs));
    if (repairArgs) {
        repairArgs->initialController = localPC;
        CreateThread(nullptr, 0, RepairRangeSpawnThread, repairArgs, 0, nullptr);
    }
}

static DWORD WINAPI ListenServerWatchThread(LPVOID)
{
    for (int i = 0; i < 80; ++i) {
        Sleep(500);

        uintptr_t world = 0;
        safe_read_t((void*)(GetImageBase() + OFF_GWORLD), world);
        if (!world) {
            if ((i % 10) == 0) log_msg("[toolkit] ListenWatch: GWorld=null\n");
            continue;
        }

        uintptr_t netDriver = 0;
        safe_read_t((void*)(world + 0x40), netDriver);
        log_msg("[toolkit] ListenWatch: World=0x%llX Name=%s NetDriver=0x%llX%s\n",
            (unsigned long long)world,
            ObjName(world).c_str(),
            (unsigned long long)netDriver,
            netDriver ? " [LISTEN READY]" : "");

        if (netDriver) {
            DumpRangeWorldCensus("listen-server-netdriver-ready", 220);
            return 0;
        }
    }

    DumpRangeWorldCensus("listen-server-netdriver-timeout", 220);
    log_msg("[toolkit] ListenWatch: timed out waiting for GWorld->NetDriver\n");
    return 0;
}

static void ForceListenServerTravel()
{
    log_msg("[toolkit] ForceListenServerTravel called\n");
    DumpNetworkRuntimeState("before-f10-network-travel");

    uintptr_t world = 0;
    safe_read_t((void*)(GetImageBase() + OFF_GWORLD), world);
    if (!world) {
        log_msg("[toolkit] ListenServer: GWorld is null\n");
        return;
    }
    log_msg("[toolkit] ListenServer: GWorld=0x%llX Name=%s\n",
        (unsigned long long)world, ObjName(world).c_str());

    uintptr_t pc = FindBestPlayerController(true, nullptr);
    if (!pc) {
        log_msg("[toolkit] ListenServer: no live PlayerController found\n");
        DumpRangeWorldCensus("listen-server-no-playercontroller", 220);
        return;
    }
    log_msg("[toolkit] ListenServer: PC=0x%llX Class=%s Name=%s\n",
        (unsigned long long)pc, ClassName(pc).c_str(), ObjName(pc).c_str());

    uintptr_t clientTravelFunc = FindFunctionByName("PlayerController", "ClientTravel");
    if (!clientTravelFunc) {
        log_msg("[toolkit] ListenServer: no ClientTravel UFunction found\n");
        return;
    }

    // The retail client path logs "LoadMap: failed to Listen" with no InitListen detail
    // because UWorld::Listen can be compiled as a no-server stub. Keep F10 aimed at an
    // external UE net server instead of repeatedly asking this client to become one.
    const wchar_t* urlW =
        L"127.0.0.1:7777"
        L"?game=/Game/GameModes/ShootingRange/ShootingRangeGameMode.ShootingRangeGameMode_C";

    wchar_t* buf = nullptr;
    FFString fs = MakeTempFString(urlW, &buf);
    auto pe = GetProcessEvent();

    struct ClientTravelParams {
        FFString URL;
        uint8_t TravelType;
        uint8_t bSeamless;
        uint8_t pad[2];
        uint32_t Guid[4];
    } params = {};
    params.URL = fs;
    params.TravelType = 0;
    params.bSeamless = false;
    log_msg("[toolkit] NetworkTravel: ClientTravel(%S)\n", urlW);
    pe(pc, clientTravelFunc, &params);

    free(buf);

    HANDLE t = CreateThread(nullptr, 0, ListenServerWatchThread, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
}

static void ForcePlayerSpawn()
{
    log_msg("[toolkit] ForcePlayerSpawn disabled; session/timer must come from server payload\n");
    return;

    // Find ShootingRangeGameMode
    uintptr_t gm = 0;
    int32_t n = GetNumObjects();
    for (int32_t i = 0; i < n && !gm; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj || IsCDOOrArchetype(obj)) continue;
        if (ClassName(obj).find("ShootingRangeGameMode") != std::string::npos)
            gm = obj;
    }
    if (!gm) { log_msg("[toolkit] ForcePlayerSpawn: No ShootingRangeGameMode found\n"); return; }
    log_msg("[toolkit] ForcePlayerSpawn: GameMode @ 0x%llX\n", (uint64_t)gm);

    // Get local PlayerController and PlayerState
    uintptr_t localPC = FindBestPlayerController(false, nullptr);
    if (!localPC) { log_msg("[toolkit] ForcePlayerSpawn: No local PlayerController\n"); return; }
    uintptr_t localPS = 0;
    safe_read_t((void*)(localPC + 0x0498), localPS);
    if (!localPS) { log_msg("[toolkit] ForcePlayerSpawn: No local PlayerState at PC+0x498\n"); return; }
    log_msg("[toolkit] ForcePlayerSpawn: PC=0x%llX PS=0x%llX\n", (uint64_t)localPC, (uint64_t)localPS);

    static uintptr_t setNextStateFunc = 0;
    static uintptr_t setNewTimeoutTimeFunc = 0;
    static uintptr_t timerExpiredFunc = 0;
    static uintptr_t goToStateAndSkipTimedEventsFunc = 0;
    static uintptr_t respawnPlayerFunc = 0;
    if (!setNextStateFunc) setNextStateFunc = FindFunctionByName("TimeGameStateComponent", "SetNextState");
    if (!setNewTimeoutTimeFunc) setNewTimeoutTimeFunc = FindFunctionByName("TimeGameStateComponent", "SetNewTimeoutTime");
    if (!timerExpiredFunc) timerExpiredFunc = FindFunctionByName("TimeGameStateComponent", "TimerExpired");
    if (!goToStateAndSkipTimedEventsFunc) goToStateAndSkipTimedEventsFunc = FindFunctionByName("TimeGameStateComponent", "GoToStateAndSkipTimedEvents");
    if (!respawnPlayerFunc) respawnPlayerFunc = FindFunctionByName("ShootingRangeGameMode_C", "RespawnPlayer");

    uintptr_t loadInState = 0;
    uintptr_t shootingRangeState = 0;
    uintptr_t spawnPointSpawner = 0;
    safe_read_t((void*)(gm + 0x0800), loadInState);
    safe_read_t((void*)(gm + 0x08D0), shootingRangeState);
    safe_read_t((void*)(gm + 0x0860), spawnPointSpawner);
    log_msg("[toolkit] ForcePlayerSpawn: LoadIn=0x%llX ShootingRangeState=0x%llX SpawnPointSpawner=0x%llX\n",
        (uint64_t)loadInState, (uint64_t)shootingRangeState, (uint64_t)spawnPointSpawner);

    auto pe = GetProcessEvent();
    if (loadInState && shootingRangeState) {
        if (setNextStateFunc) {
            struct SetNextStateParams { uintptr_t NextState; } params = { shootingRangeState };
            log_msg("[toolkit] ForcePlayerSpawn: SetNextState(GameStateShootingRange)\n");
            pe(loadInState, setNextStateFunc, &params);
        }
        if (setNewTimeoutTimeFunc) {
            struct SetNewTimeoutTimeParams { float NewTimeOutTime; } params = { 0.05f };
            log_msg("[toolkit] ForcePlayerSpawn: SetNewTimeoutTime(0.05)\n");
            pe(loadInState, setNewTimeoutTimeFunc, &params);
        }
        if (goToStateAndSkipTimedEventsFunc) {
            struct GoToStateAndSkipTimedEventsParams {
                uintptr_t NewState;
                float TimeUntilTransition;
                uint8_t pad[4];
            } params = { shootingRangeState, 0.05f, {0, 0, 0, 0} };
            log_msg("[toolkit] ForcePlayerSpawn: GoToStateAndSkipTimedEvents(GameStateShootingRange, 0.05)\n");
            pe(loadInState, goToStateAndSkipTimedEventsFunc, &params);
        }
        if (timerExpiredFunc) {
            log_msg("[toolkit] ForcePlayerSpawn: TimerExpired()\n");
            pe(loadInState, timerExpiredFunc, nullptr);
        }
    }

    if (respawnPlayerFunc && spawnPointSpawner) {
        struct RespawnPlayerParams {
            uintptr_t Player;
            uintptr_t Spawner;
            uintptr_t SpawnedPawn;
            uint8_t pad_18[0x28];
        } params = {};
        params.Player = localPS;
        params.Spawner = spawnPointSpawner;
        log_msg("[toolkit] ForcePlayerSpawn: RespawnPlayer(localPS, SpawnPointSpawn)\n");
        pe(gm, respawnPlayerFunc, &params);
        log_msg("[toolkit] ForcePlayerSpawn: RespawnPlayer returned SpawnedPawn=0x%llX\n", (uint64_t)params.SpawnedPawn);
    }

    // Read PlayersToSpawn TArray at gm+0x838
    struct TArr { uintptr_t Data; int32_t Count; int32_t Max; };
    TArr pts{};
    safe_read((void*)(gm + 0x838), &pts, sizeof(pts));
    log_msg("[toolkit] ForcePlayerSpawn: PlayersToSpawn Data=0x%llX Count=%d Max=%d\n",
        (uint64_t)pts.Data, pts.Count, pts.Max);

    if (!pts.Data || pts.Max == 0) {
        // TArray uninitialized — UE4 hasn't allocated it yet, so we can't safely inject.
        // Rely solely on the timer reset below to re-trigger HandleStartingNewPlayer,
        // which will allocate the array through UE4's own allocator.
        log_msg("[toolkit] ForcePlayerSpawn: PlayersToSpawn unallocated — skipping inject, resetting timer only\n");
    } else {
        // Check if localPS already in the list
        bool found = false;
        for (int32_t i = 0; i < pts.Count; i++) {
            uintptr_t entry = 0;
            safe_read_t((void*)(pts.Data + i * 8), entry);
            if (entry == localPS) { found = true; break; }
        }
        if (found) {
            log_msg("[toolkit] ForcePlayerSpawn: localPS already in PlayersToSpawn\n");
        } else if (pts.Count < pts.Max) {
            DWORD old;
            void* slot = (void*)(pts.Data + pts.Count * 8);
            VirtualProtect(slot, 8, PAGE_EXECUTE_READWRITE, &old);
            *(uintptr_t*)slot = localPS;
            VirtualProtect(slot, 8, old, &old);
            // Increment Count
            VirtualProtect((void*)(gm + 0x840), 4, PAGE_EXECUTE_READWRITE, &old);
            *(int32_t*)(gm + 0x840) = pts.Count + 1;
            VirtualProtect((void*)(gm + 0x840), 4, old, &old);
            log_msg("[toolkit] ForcePlayerSpawn: Added localPS to slot %d\n", pts.Count);
        } else {
            // Array full — overwrite slot 0
            DWORD old;
            VirtualProtect((void*)pts.Data, 8, PAGE_EXECUTE_READWRITE, &old);
            *(uintptr_t*)pts.Data = localPS;
            VirtualProtect((void*)pts.Data, 8, old, &old);
            log_msg("[toolkit] ForcePlayerSpawn: Array full, overwrote slot 0\n");
        }
    }

    // Fix WaitForPlayersTimeRemaining: scan GameStateLoadIn TimeGameStateComponent
    bool fixedTimer = false;
    for (int32_t i = 0; i < n && !fixedTimer; i++) {
        uintptr_t obj = GetObjectByIndex(i);
        if (!obj || IsCDOOrArchetype(obj)) continue;
        if (ClassName(obj).find("TimeGameStateComponent") == std::string::npos) continue;
        if (ObjName(obj).find("LoadIn") == std::string::npos) continue;
        log_msg("[toolkit] ForcePlayerSpawn: Found GameStateLoadIn @ 0x%llX, scanning for timer float\n", (uint64_t)obj);
        for (int off = 0x200; off < 0x800; off += 4) {
            float val = 0.0f;
            if (!safe_read((void*)(obj + off), &val, sizeof(float))) continue;
            if (val > -120.0f && val < -0.01f) {
                log_msg("[toolkit] ForcePlayerSpawn: WaitForPlayersTimeRemaining=%.3f at +0x%x, setting to 60.0\n", val, off);
                DWORD old;
                VirtualProtect((void*)(obj + off), 4, PAGE_EXECUTE_READWRITE, &old);
                *(float*)(obj + off) = 60.0f;
                VirtualProtect((void*)(obj + off), 4, old, &old);
                fixedTimer = true;
                break;
            }
        }
    }
    if (!fixedTimer)
        log_msg("[toolkit] ForcePlayerSpawn: GameStateLoadIn not found or no negative float — skipping timer fix\n");

    // Also scan the GameMode itself for the timer float (it may live there in some builds)
    if (!fixedTimer) {
        for (int off = 0x200; off < 0x900; off += 4) {
            float val = 0.0f;
            if (!safe_read((void*)(gm + off), &val, sizeof(float))) continue;
            if (val > -120.0f && val < -0.01f) {
                log_msg("[toolkit] ForcePlayerSpawn: Timer=%.3f at GameMode+0x%x, setting to 60.0\n", val, off);
                DWORD old;
                VirtualProtect((void*)(gm + off), 4, PAGE_EXECUTE_READWRITE, &old);
                *(float*)(gm + off) = 60.0f;
                VirtualProtect((void*)(gm + off), 4, old, &old);
                fixedTimer = true;
                break;
            }
        }
    }

    log_msg("[toolkit] ForcePlayerSpawn: Done (timerFixed=%d)\n", (int)fixedTimer);
}

static bool IsCurrentWorldRange(uintptr_t* outWorld = nullptr, std::string* outName = nullptr)
{
    uintptr_t base = GetImageBase();
    uintptr_t world = 0;
    safe_read_t((void*)(base + OFF_GWORLD), world);
    if (outWorld) *outWorld = world;
    if (!world) {
        if (outName) *outName = "<null>";
        return false;
    }

    std::string worldName = ObjName(world);
    if (outName) *outName = worldName;
    return worldName.find("Range") != std::string::npos ||
           worldName.find("Poveglia") != std::string::npos;
}

static void StartRangeControllerRepair(uintptr_t initialController)
{
    RepairRangeSpawnArgs* repairArgs = (RepairRangeSpawnArgs*)malloc(sizeof(RepairRangeSpawnArgs));
    if (!repairArgs) {
        log_msg("[toolkit] AutoRangeRepair: failed to allocate repair args\n");
        return;
    }
    memset(repairArgs, 0, sizeof(*repairArgs));
    repairArgs->initialController = initialController;
    HANDLE t = CreateThread(nullptr, 0, RepairRangeSpawnThread, repairArgs, 0, nullptr);
    if (t) CloseHandle(t);
}

static DWORD WINAPI AutoRangeRepairThread(LPVOID)
{
    log_msg("[toolkit] AutoRangeRepair: watching for Range world\n");

    uintptr_t lastRangeWorld = 0;
    bool wasInRange = false;

    while (true) {
        Sleep(500);

        uintptr_t world = 0;
        std::string worldName;
        bool inRange = IsCurrentWorldRange(&world, &worldName);
        if (!inRange) {
            if (wasInRange) {
                log_msg("[toolkit] AutoRangeRepair: left Range world (%s)\n", worldName.c_str());
            }
            wasInRange = false;
            continue;
        }

        if (wasInRange && world == lastRangeWorld) {
            continue;
        }

        wasInRange = true;
        lastRangeWorld = world;
        log_msg("[toolkit] AutoRangeRepair: entered Range world 0x%llX (%s)\n",
            (unsigned long long)world, worldName.c_str());

        DumpRangeWorldCensus("auto-range-entry", 220);
        StartRangeControllerRepair(FindBestPlayerController(false, nullptr));

        for (int attempt = 0; attempt < 8; ++attempt) {
            Sleep(attempt == 0 ? 250 : 1250);
            if (!IsCurrentWorldRange(nullptr, nullptr)) {
                break;
            }
            log_msg("[toolkit] AutoRangeRepair: ForcePlayerSpawn attempt %d/8\n", attempt + 1);
            ForcePlayerSpawn();
        }
    }
}

static DWORD WINAPI hotkey_thread(LPVOID)
{
    log_msg("[toolkit] Hotkeys ready: F1=Stats F2=Chars F3=Skins F4=DataAssets F5=AllUUIDs F6=ClassNames F7=ForceLocalTravel F8=RangeCensus F9=ForcePlayerSpawn F10=Connect127NetServer F11=DumpAresCode F12=BypassAresHandler\n");

    bool prev[13] = {};
    int vkeys[] = { 0, VK_F1, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_F10, VK_F11, VK_F12 };

    while (true) {
        Sleep(50);
        for (int k = 1; k <= 12; k++) {
            bool down = (GetAsyncKeyState(vkeys[k]) & 0x8000) != 0;
            if (down && !prev[k]) {
                switch (k) {
                    case 1: DumpStats();             break;
                    case 2: DumpCharacterAssets();   break;
                    case 3: DumpSkinAssets();        break;
                    case 4: DumpAllDataAssets();     break;
                    case 5: DumpAllUUIDs();          break;
                    case 6: DumpClassNames();        break;
                    case 7: ForceLocalTravel();      break;
                    case 8: DumpManualRangeCensus(); break;
                    case 9: ForcePlayerSpawn();      break;
                    case 10: ForceListenServerTravel(); break;
                    case 11: DumpAresHandlerCode();  break;
                    case 12: PatchAresHandlerBypass(); break;
                }
            }
            prev[k] = down;
        }
    }
}

// ─── OutputDebugString hooks (preserved from v1) ─────────────────────────────
struct Hook {
    void*   target    = nullptr;
    uint8_t original[12]{};
    bool    installed = false;
};

static bool install_hook(Hook& h, void* target, void* detour)
{
    h.target = target;
    DWORD old;
    if (!VirtualProtect(target, 12, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(h.original, target, 12);
    uint8_t* p = (uint8_t*)target;
    p[0] = 0x48; p[1] = 0xB8;
    memcpy(p + 2, &detour, 8);
    p[10] = 0xFF; p[11] = 0xE0;
    VirtualProtect(target, 12, old, &old);
    h.installed = true;
    return true;
}

static Hook        g_hookA, g_hookW;
static std::mutex  g_mtx;

static void WINAPI my_OutputDebugStringA(LPCSTR  lpOutputString);
static void WINAPI my_OutputDebugStringW(LPCWSTR lpOutputString);

static void print_dbg(const char* msg)
{
    std::string s(msg ? msg : "(null)");
    if (!s.empty() && s.back() == '\n') s.pop_back();
    if (!s.empty() && s.back() == '\r') s.pop_back();
    if (!s.empty()) log_msg("[ODS] %s\n", s.c_str());
}

static void reinstall_hook(Hook& h, void* detour)
{
    DWORD old;
    VirtualProtect(h.target, 12, PAGE_EXECUTE_READWRITE, &old);
    uint8_t* p = (uint8_t*)h.target;
    p[0] = 0x48; p[1] = 0xB8;
    memcpy(p + 2, &detour, 8);
    p[10] = 0xFF; p[11] = 0xE0;
    VirtualProtect(h.target, 12, old, &old);
}

static void remove_hook(Hook& h)
{
    DWORD old;
    VirtualProtect(h.target, 12, PAGE_EXECUTE_READWRITE, &old);
    memcpy(h.target, h.original, 12);
    VirtualProtect(h.target, 12, old, &old);
}

static void WINAPI my_OutputDebugStringA(LPCSTR lpOutputString)
{
    std::lock_guard<std::mutex> lk(g_mtx);
    print_dbg(lpOutputString);
    remove_hook(g_hookA);
    OutputDebugStringA(lpOutputString);
    reinstall_hook(g_hookA, (void*)my_OutputDebugStringA);
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
    remove_hook(g_hookW);
    OutputDebugStringW(lpOutputString);
    reinstall_hook(g_hookW, (void*)my_OutputDebugStringW);
}

// ─── main thread ─────────────────────────────────────────────────────────────
static DWORD WINAPI toolkit_main(LPVOID)
{
    log_init();
    open_console();
    log_msg("[toolkit] PID: %lu\n", GetCurrentProcessId());
    log_msg("[toolkit] ImageBase: 0x%llX\n", (unsigned long long)GetImageBase());

    // Hook ODS
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

    log_msg("[toolkit] Ready - F1=Stats F2=Chars F3=Skins F4=DataAssets F5=AllUUIDs F6=ClassNames F7=ForceLocalTravel F8=RangeCensus F10=Connect127NetServer F11=DumpAresCode F12=BypassAresHandler\n");
    log_msg("[toolkit] ─────────────────────────────────────────────────────────────\n");

    HANDLE ht = CreateThread(nullptr, 0, hotkey_thread, nullptr, 0, nullptr);
    if (ht) CloseHandle(ht);

    log_msg("[toolkit] AutoRangeRepair disabled; no spawn/state repair thread started\n");

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
