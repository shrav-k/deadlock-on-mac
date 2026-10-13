/* Own-window DXGI fullscreen/resize probe. No Steam, input automation or injection.
 * Logs geometry and restores windowed state on every normal error/exit path.
 * A successful API result still needs visual confirmation of full-screen coverage.
 */
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdio.h>

static LRESULT CALLBACK wndproc(HWND w, UINT m, WPARAM a, LPARAM b)
{
    return DefWindowProcW(w, m, a, b);
}

static void pump(void)
{
    MSG m;
    while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&m); DispatchMessageW(&m);
    }
}

static int geometry(HWND window, IDXGISwapChain *chain, unsigned width, unsigned height)
{
    RECT client, outer;
    DXGI_SWAP_CHAIN_DESC desc;
    BOOL fullscreen = FALSE;
    DEVMODEW mode = {0}; mode.dmSize = sizeof(mode);
    GetClientRect(window, &client); GetWindowRect(window, &outer);
    EnumDisplaySettingsW(NULL, ENUM_CURRENT_SETTINGS, &mode);
    IDXGISwapChain_GetDesc(chain, &desc);
    IDXGISwapChain_GetFullscreenState(chain, &fullscreen, NULL);
    printf("requested=%ux%u desktop=%lux%lu client=%ldx%ld window=%ld,%ld,%ld,%ld buffer=%ux%u fullscreen=%d\n",
           width,height,mode.dmPelsWidth,mode.dmPelsHeight,client.right,client.bottom,
           outer.left,outer.top,outer.right,outer.bottom,desc.BufferDesc.Width,desc.BufferDesc.Height,fullscreen);
    fflush(stdout);
    return !fullscreen || client.right!=(LONG)width || client.bottom!=(LONG)height ||
           desc.BufferDesc.Width!=width || desc.BufferDesc.Height!=height ||
           mode.dmPelsWidth!=width || mode.dmPelsHeight!=height;
}

int main(void)
{
    const unsigned sizes[][2] = {{1512,982},{1920,1080},{1920,1200},{1512,982}};
    WNDCLASSW wc = {0}; wc.lpfnWndProc=wndproc; wc.hInstance=GetModuleHandleW(NULL);
    wc.lpszClassName=L"DeadlockFullscreenProbe";
    if (!RegisterClassW(&wc)) return 1;
    HWND window=CreateWindowW(wc.lpszClassName,L"Deadlock fullscreen regression probe",
                              WS_OVERLAPPEDWINDOW|WS_VISIBLE,100,100,640,400,NULL,NULL,wc.hInstance,NULL);
    if (!window) return 2;
    DXGI_SWAP_CHAIN_DESC desc = {0};
    desc.BufferDesc.Width=640;desc.BufferDesc.Height=400;desc.BufferDesc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.SampleDesc.Count=1;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount=2;desc.OutputWindow=window;desc.Windowed=TRUE;
    desc.SwapEffect=DXGI_SWAP_EFFECT_DISCARD;desc.Flags=DXGI_SWAP_CHAIN_FLAG_ALLOW_MODE_SWITCH;
    ID3D11Device *device=NULL; ID3D11DeviceContext *context=NULL; IDXGISwapChain *chain=NULL;
    ID3D11Texture2D *buffer=NULL; ID3D11RenderTargetView *target=NULL; IDXGIOutput *output=NULL;
    HRESULT hr=D3D11CreateDeviceAndSwapChain(NULL,D3D_DRIVER_TYPE_HARDWARE,NULL,0,NULL,0,D3D11_SDK_VERSION,
                                            &desc,&chain,&device,NULL,&context);
    int failed=0;
    if (FAILED(hr)) {printf("create=%08lx\n",hr);failed=1;goto done;}
    hr=IDXGISwapChain_GetContainingOutput(chain,&output);
    if (FAILED(hr)) {failed=2;goto done;}
    for (unsigned test=0;test<sizeof(sizes)/sizeof(sizes[0]);++test) {
        DXGI_MODE_DESC request={0}, matched={0};
        request.Width=sizes[test][0];request.Height=sizes[test][1];request.Format=DXGI_FORMAT_R8G8B8A8_UNORM;
        hr=IDXGIOutput_FindClosestMatchingMode(output,&request,&matched,(IUnknown *)device);
        printf("mode[%u] match=%08lx actual=%ux%u refresh=%u/%u\n",test,hr,matched.Width,matched.Height,
               matched.RefreshRate.Numerator,matched.RefreshRate.Denominator);fflush(stdout);
        if (FAILED(hr) || matched.Width!=request.Width || matched.Height!=request.Height) {failed++;continue;}
        hr=IDXGISwapChain_ResizeBuffers(chain,2,matched.Width,matched.Height,matched.Format,DXGI_SWAP_CHAIN_FLAG_ALLOW_MODE_SWITCH);
        if (FAILED(hr)) {printf("ResizeBuffers=%08lx\n",hr);failed++;break;}
        hr=IDXGISwapChain_SetFullscreenState(chain,TRUE,output);
        printf("SetFullscreenState=%08lx\n",hr);fflush(stdout);
        if (FAILED(hr)) {failed++;continue;}
        hr=IDXGISwapChain_ResizeTarget(chain,&matched);
        printf("ResizeTarget=%08lx\n",hr);fflush(stdout);
        if (FAILED(hr)) {failed++;continue;}
        hr=IDXGISwapChain_GetBuffer(chain,0,&IID_ID3D11Texture2D,(void **)&buffer);
        if (SUCCEEDED(hr)) hr=ID3D11Device_CreateRenderTargetView(device,(ID3D11Resource *)buffer,NULL,&target);
        if (FAILED(hr)) {failed++;break;}
        for (unsigned frame=0;frame<120;++frame) {
            pump();
            float color[4]={test==0?.7f:.05f,test==1?.7f:.05f,test==2?.7f:.05f,1.0f};
            color[test%3]*=.5f+(float)(frame%60)/120.0f;
            ID3D11DeviceContext_ClearRenderTargetView(context,target,color);
            hr=IDXGISwapChain_Present(chain,1,0);
            if (FAILED(hr)) {printf("Present=%08lx\n",hr);failed++;break;}
            Sleep(16);
        }
        failed += geometry(window,chain,request.Width,request.Height);
        ID3D11RenderTargetView_Release(target);target=NULL;
        ID3D11Texture2D_Release(buffer);buffer=NULL;
    }
done:
    if (target) ID3D11RenderTargetView_Release(target);
    if (buffer) ID3D11Texture2D_Release(buffer);
    if (chain) {
        hr=IDXGISwapChain_SetFullscreenState(chain,FALSE,NULL);
        printf("restore-windowed=%08lx\n",hr);
        if (FAILED(hr)) failed++;
        IDXGISwapChain_Release(chain);
    }
    if (output) IDXGIOutput_Release(output);
    if (context) ID3D11DeviceContext_Release(context);
    if (device) ID3D11Device_Release(device);
    DestroyWindow(window);
    printf("failures=%d; API/geometry probe only, visual coverage is separate\n",failed);
    return failed?1:0;
}
