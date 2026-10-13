/* Standalone rendering smoke test. No Steam files, credentials or game data. */
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdio.h>

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM w, LPARAM l) {
    return DefWindowProcW(window, message, w, l);
}

int main(void) {
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = window_proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"DeadlockRuntimeProbe";
    if (!RegisterClassW(&wc)) return 1;
    HWND window = CreateWindowW(wc.lpszClassName, L"Deadlock runtime graphics test",
        WS_OVERLAPPEDWINDOW | WS_VISIBLE, 100, 100, 640, 400,
        NULL, NULL, wc.hInstance, NULL);
    if (!window) return 2;

    DXGI_SWAP_CHAIN_DESC desc = {0};
    desc.BufferDesc.Width = 640;
    desc.BufferDesc.Height = 400;
    desc.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.SampleDesc.Count = 1;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount = 2;
    desc.OutputWindow = window;
    desc.Windowed = TRUE;
    desc.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    ID3D11Device *device = NULL;
    ID3D11DeviceContext *context = NULL;
    IDXGISwapChain *swapchain = NULL;
    D3D_FEATURE_LEVEL level;
    HRESULT hr = D3D11CreateDeviceAndSwapChain(NULL, D3D_DRIVER_TYPE_HARDWARE,
        NULL, 0, NULL, 0, D3D11_SDK_VERSION, &desc, &swapchain,
        &device, &level, &context);
    printf("CreateDeviceAndSwapChain=0x%08lx\n", (unsigned long)hr);
    fflush(stdout);
    if (FAILED(hr)) return 3;

    IDXGIDevice *dxgi_device = NULL;
    IDXGIAdapter *adapter = NULL;
    if (SUCCEEDED(ID3D11Device_QueryInterface(device, &IID_IDXGIDevice, (void **)&dxgi_device)) &&
        SUCCEEDED(IDXGIDevice_GetAdapter(dxgi_device, &adapter))) {
        DXGI_ADAPTER_DESC gpu;
        if (SUCCEEDED(IDXGIAdapter_GetDesc(adapter, &gpu)))
            printf("Adapter=%ls\nFeatureLevel=0x%x\n", gpu.Description, level);
    }
    ID3D11Texture2D *buffer = NULL;
    ID3D11RenderTargetView *target = NULL;
    hr = IDXGISwapChain_GetBuffer(swapchain, 0, &IID_ID3D11Texture2D, (void **)&buffer);
    if (SUCCEEDED(hr)) hr = ID3D11Device_CreateRenderTargetView(device,
        (ID3D11Resource *)buffer, NULL, &target);
    printf("CreateRenderTarget=0x%08lx\n", (unsigned long)hr);
    if (FAILED(hr)) return 4;
    for (int frame = 0; frame < 120; ++frame) {
        MSG message;
        while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
        float color[4] = {0.05f, 0.2f + frame / 240.0f, 0.4f, 1.0f};
        ID3D11DeviceContext_ClearRenderTargetView(context, target, color);
        hr = IDXGISwapChain_Present(swapchain, 1, 0);
        if (FAILED(hr)) {
            printf("Present[%d]=0x%08lx\n", frame, (unsigned long)hr);
            return 5;
        }
        Sleep(16);
    }
    puts("PASS: 120 frames presented. This does not establish game compatibility.");
    ID3D11RenderTargetView_Release(target);
    ID3D11Texture2D_Release(buffer);
    if (adapter) IDXGIAdapter_Release(adapter);
    if (dxgi_device) IDXGIDevice_Release(dxgi_device);
    IDXGISwapChain_Release(swapchain);
    ID3D11DeviceContext_Release(context);
    ID3D11Device_Release(device);
    DestroyWindow(window);
    return 0;
}
