/* Read-only display inventory through Win32, DXGI and the game's SDL3 build.
 * Creates no game/window, changes no display mode, and never loads Steam APIs.
 * SDL functions are resolved dynamically; signatures follow the SDL3 public API.
 * Usage: display-inventory-probe.exe Z:\absolute\path\to\SDL3.dll
 */
#define COBJMACROS
#include <windows.h>
#include <windowsx.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned monitor_count;
static bool close_window;

static LRESULT CALLBACK window_proc(HWND window, UINT msg, WPARAM a, LPARAM b)
{
    if (msg == WM_CLOSE || (msg == WM_KEYDOWN && a == VK_ESCAPE)) { close_window = true; return 0; }
    if (msg == WM_LBUTTONDOWN) {
        printf("pointer_click=%d,%d\n", GET_X_LPARAM(b), GET_Y_LPARAM(b)); fflush(stdout);
    }
    if (msg == WM_ACTIVATE) { printf("window_active=%u\n", LOWORD(a) != WA_INACTIVE); fflush(stdout); }
    return DefWindowProcW(window, msg, a, b);
}

/* Owned diagnostic window, no interaction with another process. No mode switch,
 * cursor capture or always-on-top flag. Escape or a 90-second deadline closes it. */
static int window_test(int x, int y, int width, int height)
{
    if (width < 640 || height < 480 || width > 7680 || height > 4320) return 1;
    WNDCLASSW wc = {0}; wc.lpfnWndProc = window_proc; wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"DeadlockDisplayTest"; wc.hCursor = LoadCursorW(NULL, IDC_ARROW);
    if (!RegisterClassW(&wc)) return 1;
    HWND window = CreateWindowW(wc.lpszClassName, L"Deadlock display test — Escape to close", WS_POPUP,
                                x, y, width, height, NULL, NULL, wc.hInstance, NULL);
    if (!window) return 1;
    DXGI_SWAP_CHAIN_DESC desc = {0};
    desc.BufferDesc.Width = width; desc.BufferDesc.Height = height;
    desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM; desc.SampleDesc.Count = 1;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT; desc.BufferCount = 2;
    desc.OutputWindow = window; desc.Windowed = TRUE; desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    ID3D11Device *device = NULL; ID3D11DeviceContext *context = NULL; IDXGISwapChain *chain = NULL;
    ID3D11Texture2D *buffer = NULL;
    HRESULT hr = D3D11CreateDeviceAndSwapChain(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, NULL, 0,
                    D3D11_SDK_VERSION, &desc, &chain, &device, NULL, &context);
    int failed = FAILED(hr);
    if (!failed) {
        hr = IDXGISwapChain_GetBuffer(chain, 0, &IID_ID3D11Texture2D, (void **)&buffer);
        failed = FAILED(hr);
    }
    uint32_t *pixels = failed ? NULL : malloc((size_t)width * height * 4);
    if (!pixels) failed = 1;
    if (!failed) {
        for (int py = 0; py < height; ++py) for (int px = 0; px < width; ++px) {
            uint32_t color = (px % 100 == 0 || py % 100 == 0) ? 0xff555555 : 0xff181818;
            if (px < 6 || py < 6 || px >= width - 6 || py >= height - 6) color = 0xffffffff;
            if (abs(px - 80) < 24 && abs(py - 80) < 24) color = 0xff4444ff;
            if (abs(px - (width - 80)) < 24 && abs(py - 80) < 24) color = 0xff44ff44;
            if (abs(px - 80) < 24 && abs(py - (height - 80)) < 24) color = 0xffff8844;
            if (abs(px - (width - 80)) < 24 && abs(py - (height - 80)) < 24) color = 0xff44ffff;
            pixels[(size_t)py * width + px] = color;
        }
        ShowWindow(window, SW_SHOW);
        RECT rect, client; GetWindowRect(window, &rect); GetClientRect(window, &client);
        D3D11_TEXTURE2D_DESC texture; ID3D11Texture2D_GetDesc(buffer, &texture);
        printf("test_window=%ld,%ld,%ld,%ld client=%ldx%ld buffer=%ux%u\n", rect.left, rect.top,
               rect.right, rect.bottom, client.right, client.bottom, texture.Width, texture.Height); fflush(stdout);
        ULONGLONG end = GetTickCount64() + 90000;
        while (!close_window && GetTickCount64() < end) {
            MSG message;
            while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&message); DispatchMessageW(&message); }
            ID3D11DeviceContext_UpdateSubresource(context, (ID3D11Resource *)buffer, 0, NULL, pixels, width * 4, 0);
            hr = IDXGISwapChain_Present(chain, 1, 0);
            if (FAILED(hr)) { failed = 1; break; }
            Sleep(16);
        }
    }
    free(pixels);
    if (buffer) ID3D11Texture2D_Release(buffer);
    if (chain) IDXGISwapChain_Release(chain);
    if (context) ID3D11DeviceContext_Release(context);
    if (device) ID3D11Device_Release(device);
    DestroyWindow(window);
    printf("test_window_closed=yes result=%d\n", failed); fflush(stdout);
    return failed;
}

static BOOL CALLBACK monitor(HMONITOR handle, HDC dc, RECT *rect, LPARAM user)
{
    (void)dc; (void)rect; (void)user;
    MONITORINFOEXW info = {0}; info.cbSize = sizeof(info);
    if (!GetMonitorInfoW(handle, (MONITORINFO *)&info)) return FALSE;
    DEVMODEW mode = {0}; mode.dmSize = sizeof(mode);
    if (!EnumDisplaySettingsW(info.szDevice, ENUM_CURRENT_SETTINGS, &mode)) return FALSE;
    printf("win32 index=%u device=%ls primary=%u bounds=%ld,%ld,%ld,%ld current=%lux%lu refresh=%lu\n",
           monitor_count++, info.szDevice, !!(info.dwFlags & MONITORINFOF_PRIMARY),
           info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom,
           mode.dmPelsWidth, mode.dmPelsHeight, mode.dmDisplayFrequency);
    return TRUE;
}

static int dxgi(void)
{
    IDXGIFactory *factory = NULL;
    HRESULT result = CreateDXGIFactory(&IID_IDXGIFactory, (void **)&factory);
    if (FAILED(result)) return 1;
    int failed = 0;
    for (UINT a = 0; a < 16; ++a) {
        IDXGIAdapter *adapter = NULL;
        result = IDXGIFactory_EnumAdapters(factory, a, &adapter);
        if (result == DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(result)) { failed = 1; break; }
        for (UINT o = 0; o < 32; ++o) {
            IDXGIOutput *output = NULL;
            result = IDXGIAdapter_EnumOutputs(adapter, o, &output);
            if (result == DXGI_ERROR_NOT_FOUND) break;
            if (FAILED(result)) { failed = 1; break; }
            DXGI_OUTPUT_DESC desc = {0};
            result = IDXGIOutput_GetDesc(output, &desc);
            if (FAILED(result)) failed = 1;
            else printf("dxgi adapter=%u output=%u device=%ls attached=%d bounds=%ld,%ld,%ld,%ld\n",
                        a, o, desc.DeviceName, desc.AttachedToDesktop,
                        desc.DesktopCoordinates.left, desc.DesktopCoordinates.top,
                        desc.DesktopCoordinates.right, desc.DesktopCoordinates.bottom);
            IDXGIOutput_Release(output);
        }
        IDXGIAdapter_Release(adapter);
    }
    IDXGIFactory_Release(factory);
    return failed;
}

#define LOAD(ret, name, args) \
    ret (__cdecl *name) args = (void *)GetProcAddress(module, #name); \
    if (!name) { fprintf(stderr, "Missing SDL3 export: %s\n", #name); FreeLibrary(module); return 2; }

int wmain(int argc, wchar_t **argv)
{
    int selected = -1;
    if (argc == 4 && !wcscmp(argv[2], L"--window-index")) {
        wchar_t *end; long value = wcstol(argv[3], &end, 10);
        if (*end || value < 0 || value >= 32) return 2;
        selected = (int)value;
    } else if (argc != 2) { fprintf(stderr, "Pass the absolute Windows path to SDL3.dll\n"); return 2; }
    if (!SetProcessDPIAware()) { fprintf(stderr, "Could not set probe DPI awareness\n"); return 2; }
    UINT (WINAPI *dpi_for_system)(void) = (void *)GetProcAddress(GetModuleHandleW(L"user32.dll"), "GetDpiForSystem");
    if (!dpi_for_system) { fprintf(stderr, "GetDpiForSystem unavailable\n"); return 2; }
    printf("win32 dpi_awareness=system dpi=%u\n", dpi_for_system());
    if (!EnumDisplayMonitors(NULL, NULL, monitor, 0) || !monitor_count) return 1;
    int failed = dxgi();
    HMODULE module = LoadLibraryExW(argv[1], NULL,
                                   LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) { fprintf(stderr, "SDL3 load failed: %lu\n", GetLastError()); return 2; }
    typedef struct { int x, y, w, h; } Rect;
    LOAD(bool, SDL_Init, (uint32_t));
    LOAD(void, SDL_Quit, (void));
    LOAD(uint32_t *, SDL_GetDisplays, (int *));
    LOAD(uint32_t, SDL_GetPrimaryDisplay, (void));
    LOAD(const char *, SDL_GetDisplayName, (uint32_t));
    LOAD(bool, SDL_GetDisplayBounds, (uint32_t, Rect *));
    LOAD(uint32_t, SDL_GetDisplayProperties, (uint32_t));
    LOAD(void *, SDL_GetPointerProperty, (uint32_t, const char *, void *));
    LOAD(void, SDL_free, (void *));
    LOAD(const char *, SDL_GetError, (void));
    LOAD(int, SDL_GetVersion, (void));
    printf("sdl version=%d\n", SDL_GetVersion());
    if (!SDL_Init(0x20u)) { fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError()); FreeLibrary(module); return 1; }
    int count = 0;
    uint32_t *ids = SDL_GetDisplays(&count);
    if (!ids || count < 1 || count > 32 || selected >= count) failed = 1;
    else for (int i = 0; i < count; ++i) {
        Rect rect = {0};
        MONITORINFOEXW info = {0}; info.cbSize = sizeof(info);
        HMONITOR handle = SDL_GetPointerProperty(SDL_GetDisplayProperties(ids[i]), "SDL.display.windows.hmonitor", NULL);
        const char *name = SDL_GetDisplayName(ids[i]);
        if (!SDL_GetDisplayBounds(ids[i], &rect) || !handle || !GetMonitorInfoW(handle, (MONITORINFO *)&info) || !name) {
            failed = 1; break;
        }
        printf("sdl index=%d instance=%u primary=%u name=%s device=%ls bounds=%d,%d,%d,%d\n",
               i, ids[i], ids[i] == SDL_GetPrimaryDisplay(), name, info.szDevice,
               rect.x, rect.y, rect.w, rect.h);
        if (selected == i) failed |= window_test(rect.x, rect.y, rect.w, rect.h);
    }
    SDL_free(ids);
    SDL_Quit();
    FreeLibrary(module);
    printf("inventory_collected=%s visual_placement_verified=no game_selection_verified=no\n", failed ? "no" : "yes");
    return failed;
}
