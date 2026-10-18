/* Isolated D3D12 capability gate. No Steam, game, save, or registry access.
 * A successful device is insufficient: submit a GPU clear/copy and check pixels.
 * The optional clear-only control distinguishes basic execution from shaders.
 * --present adds a bounded windowed swapchain check, not a gameplay benchmark. */
#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_4.h>
#include <d3dcompiler.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>

/* Mesh/amplification shaders use pipeline streams, not extra fields in this
 * published legacy ABI. Do not change the probe to accommodate a broken driver. */
_Static_assert(offsetof(D3D12_GRAPHICS_PIPELINE_STATE_DESC, StreamOutput) == 88,
               "The probe requires Microsoft's standard x64 graphics PSO ABI");

#define CHECK(call) do { HRESULT hr_ = (call); \
    printf("%s: 0x%08lx\n", #call, (unsigned long)hr_); fflush(stdout); \
    if (FAILED(hr_)) return 2; } while (0)

static int present_frames(IDXGIFactory1 *factory, ID3D12Device *device,
        ID3D12CommandQueue *queue, ID3D12CommandAllocator *allocator,
        ID3D12GraphicsCommandList *list, ID3D12PipelineState *pipeline,
        ID3D12RootSignature *signature, D3D12_CPU_DESCRIPTOR_HANDLE handle,
        ID3D12Fence *fence, HANDLE event)
{
    WNDCLASSA klass = {0};
    RECT bounds = {0, 0, 320, 240};
    HWND window;
    IDXGIFactory2 *factory2 = NULL;
    IDXGISwapChain1 *chain1 = NULL;
    IDXGISwapChain3 *chain = NULL;
    DXGI_SWAP_CHAIN_DESC1 desc = {0};
    const float red[] = {1, 0, 0, 1};
    klass.lpfnWndProc = DefWindowProcA;
    klass.hInstance = GetModuleHandleA(NULL);
    klass.lpszClassName = "LauncherD3D12Probe";
    if (!RegisterClassA(&klass)) return 7;
    AdjustWindowRect(&bounds, WS_OVERLAPPEDWINDOW, FALSE);
    window = CreateWindowA(klass.lpszClassName, "Isolated D3D12 qualification", WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, bounds.right-bounds.left, bounds.bottom-bounds.top,
        NULL, NULL, klass.hInstance, NULL);
    if (!window) return 7;
    ShowWindow(window, SW_SHOWNORMAL);
    CHECK(IDXGIFactory1_QueryInterface(factory, &IID_IDXGIFactory2, (void **)&factory2));
    desc.Width = 320; desc.Height = 240;
    desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.SampleDesc.Count = 1;
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    desc.BufferCount = 2;
    desc.Scaling = DXGI_SCALING_STRETCH;
    desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    CHECK(IDXGIFactory2_CreateSwapChainForHwnd(factory2, (IUnknown *)queue, window,
                                             &desc, NULL, NULL, &chain1));
    CHECK(IDXGISwapChain1_QueryInterface(chain1, &IID_IDXGISwapChain3, (void **)&chain));
    for (UINT frame = 0; frame < 60; ++frame) {
        MSG message;
        ID3D12Resource *buffer = NULL;
        D3D12_RESOURCE_BARRIER barrier = {0};
        D3D12_VIEWPORT viewport = {0, 0, 320, 240, 0, 1};
        D3D12_RECT scissor = {0, 0, 320, 240};
        ID3D12CommandList *lists[] = {(ID3D12CommandList *)list};
        while (PeekMessageA(&message, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&message); DispatchMessageA(&message);
        }
        if (!IsWindow(window)) return 7;
        CHECK(IDXGISwapChain3_GetBuffer(chain, IDXGISwapChain3_GetCurrentBackBufferIndex(chain),
                                        &IID_ID3D12Resource, (void **)&buffer));
        CHECK(ID3D12CommandAllocator_Reset(allocator));
        CHECK(ID3D12GraphicsCommandList_Reset(list, allocator, pipeline));
        barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        barrier.Transition.pResource = buffer;
        barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_PRESENT;
        barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_RENDER_TARGET;
        ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
        ID3D12Device_CreateRenderTargetView(device, buffer, NULL, handle);
        ID3D12GraphicsCommandList_ClearRenderTargetView(list, handle, red, 0, NULL);
        ID3D12GraphicsCommandList_SetGraphicsRootSignature(list, signature);
        ID3D12GraphicsCommandList_RSSetViewports(list, 1, &viewport);
        ID3D12GraphicsCommandList_RSSetScissorRects(list, 1, &scissor);
        ID3D12GraphicsCommandList_OMSetRenderTargets(list, 1, &handle, FALSE, NULL);
        ID3D12GraphicsCommandList_IASetPrimitiveTopology(list, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        ID3D12GraphicsCommandList_DrawInstanced(list, 3, 1, 0, 0);
        barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
        barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_PRESENT;
        ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
        CHECK(ID3D12GraphicsCommandList_Close(list));
        ID3D12CommandQueue_ExecuteCommandLists(queue, 1, lists);
        CHECK(IDXGISwapChain3_Present(chain, 1, 0));
        CHECK(ID3D12CommandQueue_Signal(queue, fence, frame + 2));
        CHECK(ID3D12Fence_SetEventOnCompletion(fence, frame + 2, event));
        if (WaitForSingleObject(event, 10000) != WAIT_OBJECT_0) return 5;
        ID3D12Resource_Release(buffer);
    }
    IDXGISwapChain3_Release(chain);
    IDXGISwapChain1_Release(chain1);
    IDXGIFactory2_Release(factory2);
    DestroyWindow(window);
    UnregisterClassA(klass.lpszClassName, klass.hInstance);
    puts("PASS: 60 windowed flip-discard presents, bounded GPU waits, window destroyed");
    return 0;
}

int main(int argc, char **argv)
{
    IDXGIFactory1 *factory = NULL;
    IDXGIAdapter1 *adapter = NULL;
    ID3D12Device *device = NULL;
    ID3D12CommandQueue *queue = NULL;
    ID3D12CommandAllocator *allocator = NULL;
    ID3D12GraphicsCommandList *list = NULL;
    ID3D12Resource *texture = NULL, *readback = NULL;
    ID3D12DescriptorHeap *descriptors = NULL;
    ID3D12Fence *fence = NULL;
    ID3D12RootSignature *signature = NULL;
    ID3D12PipelineState *pipeline = NULL;
    ID3DBlob *vs = NULL, *ps = NULL, *serialized = NULL, *error = NULL;
    DXGI_ADAPTER_DESC1 adapter_desc;
    HANDLE event;
    UINT row_count;
    UINT64 row_size, total;
    unsigned char *pixels = NULL;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint;
    D3D12_CPU_DESCRIPTOR_HANDLE handle;
    D3D12_COMMAND_QUEUE_DESC queue_desc = {0};
    D3D12_DESCRIPTOR_HEAP_DESC descriptor_desc = {0};
    D3D12_HEAP_PROPERTIES heap = {0};
    D3D12_RESOURCE_DESC resource = {0};
    D3D12_CLEAR_VALUE clear = {0};
    D3D12_RESOURCE_BARRIER barrier = {0};
    D3D12_TEXTURE_COPY_LOCATION source = {0}, destination = {0};
    D3D12_RANGE range;
    const float red[] = {1, 0, 0, 1};
    const int clear_only = argc == 2 && !strcmp(argv[1], "--clear-only");
    const int present = argc == 2 && !strcmp(argv[1], "--present");
    if (argc > 2 || (argc == 2 && !clear_only && !present)) return 8;
    setvbuf(stdout, NULL, _IONBF, 0);
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    CHECK(CreateDXGIFactory1(&IID_IDXGIFactory1, (void **)&factory));
    CHECK(IDXGIFactory1_EnumAdapters1(factory, 0, &adapter));
    CHECK(IDXGIAdapter1_GetDesc1(adapter, &adapter_desc));
    printf("Adapter: %ls vendor=%04x device=%04x software=%u\n",
           adapter_desc.Description, adapter_desc.VendorId, adapter_desc.DeviceId,
           !!(adapter_desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE));
    if (adapter_desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) return 3;
    CHECK(D3D12CreateDevice((IUnknown *)adapter, D3D_FEATURE_LEVEL_12_0,
                           &IID_ID3D12Device, (void **)&device));
    queue_desc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    CHECK(ID3D12Device_CreateCommandQueue(device, &queue_desc, &IID_ID3D12CommandQueue, (void **)&queue));
    CHECK(ID3D12Device_CreateCommandAllocator(device, D3D12_COMMAND_LIST_TYPE_DIRECT,
                                             &IID_ID3D12CommandAllocator, (void **)&allocator));
    CHECK(ID3D12Device_CreateCommandList(device, 0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator,
                                       NULL, &IID_ID3D12GraphicsCommandList, (void **)&list));
    heap.Type = D3D12_HEAP_TYPE_DEFAULT;
    resource.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    resource.Width = resource.Height = 4;
    resource.DepthOrArraySize = resource.MipLevels = 1;
    resource.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    resource.SampleDesc.Count = 1;
    resource.Flags = D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;
    clear.Format = resource.Format;
    clear.Color[0] = clear.Color[3] = 1;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &resource,
        D3D12_RESOURCE_STATE_RENDER_TARGET, &clear, &IID_ID3D12Resource, (void **)&texture));
    descriptor_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_RTV;
    descriptor_desc.NumDescriptors = 1;
    CHECK(ID3D12Device_CreateDescriptorHeap(device, &descriptor_desc,
                                           &IID_ID3D12DescriptorHeap, (void **)&descriptors));
    descriptors->lpVtbl->GetCPUDescriptorHandleForHeapStart(descriptors, &handle);
    ID3D12Device_CreateRenderTargetView(device, texture, NULL, handle);
    ID3D12GraphicsCommandList_ClearRenderTargetView(list, handle, red, 0, NULL);
    if (!clear_only) {
        const char *shader =
            "float4 vs(uint id:SV_VertexID):SV_Position {"
            "float2 p=float2((id<<1)&2,id&2);return float4(p*2-1,0,1);}"
            "float4 ps():SV_Target {return float4(0,1,0,1);}";
        D3D12_ROOT_SIGNATURE_DESC root = {0};
        D3D12_GRAPHICS_PIPELINE_STATE_DESC pso = {0};
        D3D12_VIEWPORT viewport = {0, 0, 4, 4, 0, 1};
        D3D12_RECT scissor = {0, 0, 4, 4};
        CHECK(D3DCompile(shader, strlen(shader), "probe", NULL, NULL, "vs", "vs_5_0", 0, 0, &vs, &error));
        if (error) { ID3D10Blob_Release(error); error = NULL; }
        CHECK(D3DCompile(shader, strlen(shader), "probe", NULL, NULL, "ps", "ps_5_0", 0, 0, &ps, &error));
        if (error) { ID3D10Blob_Release(error); error = NULL; }
        CHECK(D3D12SerializeRootSignature(&root, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &error));
        if (error) { ID3D10Blob_Release(error); error = NULL; }
        CHECK(ID3D12Device_CreateRootSignature(device, 0, ID3D10Blob_GetBufferPointer(serialized),
            ID3D10Blob_GetBufferSize(serialized), &IID_ID3D12RootSignature, (void **)&signature));
        pso.pRootSignature = signature;
        pso.VS = (D3D12_SHADER_BYTECODE){ID3D10Blob_GetBufferPointer(vs), ID3D10Blob_GetBufferSize(vs)};
        pso.PS = (D3D12_SHADER_BYTECODE){ID3D10Blob_GetBufferPointer(ps), ID3D10Blob_GetBufferSize(ps)};
        pso.BlendState.RenderTarget[0].RenderTargetWriteMask = D3D12_COLOR_WRITE_ENABLE_ALL;
        pso.BlendState.RenderTarget[0].SrcBlend = D3D12_BLEND_ONE;
        pso.BlendState.RenderTarget[0].DestBlend = D3D12_BLEND_ZERO;
        pso.BlendState.RenderTarget[0].BlendOp = D3D12_BLEND_OP_ADD;
        pso.BlendState.RenderTarget[0].SrcBlendAlpha = D3D12_BLEND_ONE;
        pso.BlendState.RenderTarget[0].DestBlendAlpha = D3D12_BLEND_ZERO;
        pso.BlendState.RenderTarget[0].BlendOpAlpha = D3D12_BLEND_OP_ADD;
        pso.BlendState.RenderTarget[0].LogicOp = D3D12_LOGIC_OP_NOOP;
        pso.DepthStencilState.DepthWriteMask = D3D12_DEPTH_WRITE_MASK_ZERO;
        pso.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_ALWAYS;
        pso.DepthStencilState.FrontFace.StencilFailOp = D3D12_STENCIL_OP_KEEP;
        pso.DepthStencilState.FrontFace.StencilDepthFailOp = D3D12_STENCIL_OP_KEEP;
        pso.DepthStencilState.FrontFace.StencilPassOp = D3D12_STENCIL_OP_KEEP;
        pso.DepthStencilState.FrontFace.StencilFunc = D3D12_COMPARISON_FUNC_ALWAYS;
        pso.DepthStencilState.BackFace = pso.DepthStencilState.FrontFace;
        pso.SampleMask = UINT_MAX;
        pso.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
        pso.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
        pso.RasterizerState.DepthClipEnable = TRUE;
        pso.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
        pso.NumRenderTargets = 1;
        pso.RTVFormats[0] = DXGI_FORMAT_R8G8B8A8_UNORM;
        pso.SampleDesc.Count = 1;
        CHECK(ID3D12Device_CreateGraphicsPipelineState(device, &pso, &IID_ID3D12PipelineState, (void **)&pipeline));
        ID3D12GraphicsCommandList_SetPipelineState(list, pipeline);
        ID3D12GraphicsCommandList_SetGraphicsRootSignature(list, signature);
        ID3D12GraphicsCommandList_RSSetViewports(list, 1, &viewport);
        ID3D12GraphicsCommandList_RSSetScissorRects(list, 1, &scissor);
        ID3D12GraphicsCommandList_OMSetRenderTargets(list, 1, &handle, FALSE, NULL);
        ID3D12GraphicsCommandList_IASetPrimitiveTopology(list, D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        ID3D12GraphicsCommandList_DrawInstanced(list, 3, 1, 0, 0);
    }
    ID3D12Device_GetCopyableFootprints(device, &resource, 0, 1, 0, &footprint, &row_count, &row_size, &total);
    heap.Type = D3D12_HEAP_TYPE_READBACK;
    resource = (D3D12_RESOURCE_DESC){0};
    resource.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    resource.Width = total;
    resource.Height = resource.DepthOrArraySize = resource.MipLevels = resource.SampleDesc.Count = 1;
    resource.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    CHECK(ID3D12Device_CreateCommittedResource(device, &heap, D3D12_HEAP_FLAG_NONE, &resource,
        D3D12_RESOURCE_STATE_COPY_DEST, NULL, &IID_ID3D12Resource, (void **)&readback));
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = texture;
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_RENDER_TARGET;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    ID3D12GraphicsCommandList_ResourceBarrier(list, 1, &barrier);
    source.pResource = texture;
    source.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    destination.pResource = readback;
    destination.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    destination.PlacedFootprint = footprint;
    ID3D12GraphicsCommandList_CopyTextureRegion(list, &destination, 0, 0, 0, &source, NULL);
    CHECK(ID3D12GraphicsCommandList_Close(list));
    CHECK(ID3D12Device_CreateFence(device, 0, D3D12_FENCE_FLAG_NONE, &IID_ID3D12Fence, (void **)&fence));
    event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!event) return 4;
    ID3D12CommandList *lists[] = {(ID3D12CommandList *)list};
    ID3D12CommandQueue_ExecuteCommandLists(queue, 1, lists);
    CHECK(ID3D12CommandQueue_Signal(queue, fence, 1));
    CHECK(ID3D12Fence_SetEventOnCompletion(fence, 1, event));
    if (WaitForSingleObject(event, 10000) != WAIT_OBJECT_0) { puts("FAIL: GPU fence timeout"); return 5; }
    range.Begin = 0; range.End = (SIZE_T)total;
    CHECK(ID3D12Resource_Map(readback, 0, &range, (void **)&pixels));
    for (UINT y = 0; y < 4; ++y) for (UINT x = 0; x < 4; ++x) {
        unsigned char *p = pixels + footprint.Offset + y * footprint.Footprint.RowPitch + x * 4;
        if (p[0] != (clear_only ? 255 : 0) || p[1] != (clear_only ? 0 : 255) || p[2] != 0 || p[3] != 255) {
            printf("FAIL: pixel %u,%u = %u,%u,%u,%u\n", x, y, p[0], p[1], p[2], p[3]); return 6;
        }
    }
    range.End = 0;
    ID3D12Resource_Unmap(readback, 0, &range);
    if (present) {
        int result = present_frames(factory, device, queue, allocator, list, pipeline,
                                    signature, handle, fence, event);
        if (result) return result;
    }
    CHECK(ID3D12Device_GetDeviceRemovedReason(device));
    CloseHandle(event);
    ID3D12Fence_Release(fence);
    ID3D12GraphicsCommandList_Release(list);
    ID3D12CommandAllocator_Release(allocator);
    ID3D12Resource_Release(readback);
    ID3D12DescriptorHeap_Release(descriptors);
    ID3D12Resource_Release(texture);
    ID3D12CommandQueue_Release(queue);
    if (pipeline) ID3D12PipelineState_Release(pipeline);
    if (signature) ID3D12RootSignature_Release(signature);
    if (serialized) ID3D10Blob_Release(serialized);
    if (vs) ID3D10Blob_Release(vs);
    if (ps) ID3D10Blob_Release(ps);
    ID3D12Device_Release(device);
    IDXGIAdapter1_Release(adapter);
    IDXGIFactory1_Release(factory);
    puts(clear_only ? "PASS: hardware D3D12 FL12_0, clear/copy, fence, 16 exact red pixels, orderly release"
                    : "PASS: hardware D3D12 FL12_0, DXBC shaders, triangle/copy, fence, 16 exact green pixels, orderly release");
    return 0;
}
