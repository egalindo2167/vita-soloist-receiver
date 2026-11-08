/* Dedicated Soloist process-loopback helper. Public WASAPI/COM APIs only.
 * Build recipe: tools/build_windows_capture.py. No virtual driver is bundled.
 * Process capture ABI: Microsoft AUDIOCLIENT_ACTIVATION_PARAMS (build 20348+).
 */
#define COBJMACROS
#define INITGUID
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audiopolicy.h>
#include <endpointvolume.h>
#include <functiondiscoverykeys_devpkey.h>
#include <propvarutil.h>
#include <tlhelp32.h>
#include <avrt.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <wchar.h>
#include <string.h>
#include "capture_policy.h"

static const char VERSION[]="1.1";
/* Layout matches audioclientactivationparams.h; older MinGW headers omit it. */
typedef struct { DWORD target;int mode; } ProcessLoopbackParams;
typedef struct { int type;union { ProcessLoopbackParams process; }; } ActivationParams;
_Static_assert(sizeof(ActivationParams)==12,"Windows process-loopback activation ABI");
static volatile LONG stopping;
static HANDLE audio_event;
static BOOL WINAPI console_stop(DWORD event) {
    if(event==CTRL_C_EVENT || event==CTRL_BREAK_EVENT || event==CTRL_CLOSE_EVENT) {
        InterlockedExchange(&stopping,1);return TRUE;
    }
    return FALSE;
}
static uint64_t filetime_value(FILETIME f) { return (uint64_t)f.dwHighDateTime<<32|f.dwLowDateTime; }
static int write_bytes(const void *data,size_t size) {
    const BYTE *p=data;HANDLE out=GetStdHandle(STD_OUTPUT_HANDLE);
    while(size) { DWORD n=0,want=(DWORD)(size>1048576?1048576:size);
        if(!WriteFile(out,p,want,&n,NULL) || !n)return 0;p+=n;size-=n; }
    return 1;
}
static void json_string(const wchar_t *text) {
    char utf8[16384];int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,text,-1,utf8,sizeof(utf8),NULL,NULL);
    if(!size)strcpy(utf8,"?");
    putchar('"');
    for(const unsigned char *p=(unsigned char *)utf8;*p;++p) {
        if(*p=='"' || *p=='\\')printf("\\%c",*p);
        else if(*p<32)printf("\\u%04x",*p);else putchar(*p);
    }
    putchar('"');
}
static void report_error(int code,HRESULT hr) {
    fprintf(stderr,"{\"event\":\"error\",\"code\":%d,\"hresult\":%lu}\n",code,(unsigned long)hr);fflush(stderr);
}
static void startup(int code,HRESULT hr) {
    uint32_t out[4]={0,1,(uint32_t)code,(uint32_t)hr};memcpy(out,"VACP",4);write_bytes(out,sizeof(out));
}
static DWORD os_build(void) {
    typedef LONG (WINAPI *GetVersionFn)(OSVERSIONINFOW *);
    HMODULE module=GetModuleHandleW(L"ntdll.dll");
    GetVersionFn get=(GetVersionFn)(void *)GetProcAddress(module,"RtlGetVersion");
    OSVERSIONINFOW value={0};value.dwOSVersionInfoSize=sizeof(value);
    return get && !get(&value)?value.dwBuildNumber:0;
}
static HRESULT enumerator(IMMDeviceEnumerator **out) {
    return CoCreateInstance(&CLSID_MMDeviceEnumerator,NULL,CLSCTX_ALL,&IID_IMMDeviceEnumerator,(void **)out);
}
static void device_name(IMMDevice *device,wchar_t name[4096]) {
    IPropertyStore *store=NULL;PROPVARIANT value;PropVariantInit(&value);wcscpy(name,L"Unnamed output");
    if(SUCCEEDED(IMMDevice_OpenPropertyStore(device,STGM_READ,&store))) {
        if(SUCCEEDED(IPropertyStore_GetValue(store,&PKEY_Device_FriendlyName,&value)) && value.vt==VT_LPWSTR && value.pwszVal)
            wcsncpy(name,value.pwszVal,4095);
        name[4095]=0;PropVariantClear(&value);IPropertyStore_Release(store);
    }
}
static HRESULT get_device(IMMDeviceEnumerator *enumerate,const wchar_t *id,IMMDevice **device) {
    IMMEndpoint *endpoint=NULL;EDataFlow flow=eAll;DWORD state=0;
    HRESULT hr=IMMDeviceEnumerator_GetDevice(enumerate,id,device);if(FAILED(hr))return hr;
    hr=IMMDevice_GetState(*device,&state);
    if(SUCCEEDED(hr))hr=IMMDevice_QueryInterface(*device,&IID_IMMEndpoint,(void **)&endpoint);
    if(SUCCEEDED(hr))hr=IMMEndpoint_GetDataFlow(endpoint,&flow);
    if(endpoint)IMMEndpoint_Release(endpoint);
    if(FAILED(hr) || !(state&DEVICE_STATE_ACTIVE) || flow!=eRender) {
        IMMDevice_Release(*device);*device=NULL;return E_NOTFOUND;
    }
    return S_OK;
}
static int list_devices(void) {
    IMMDeviceEnumerator *enumerate=NULL;IMMDeviceCollection *devices=NULL;UINT count=0;HRESULT hr=enumerator(&enumerate);
    if(SUCCEEDED(hr))hr=IMMDeviceEnumerator_EnumAudioEndpoints(enumerate,eRender,DEVICE_STATE_ACTIVE,&devices);
    if(SUCCEEDED(hr))hr=IMMDeviceCollection_GetCount(devices,&count);
    if(FAILED(hr)) { printf("{\"format\":1,\"code\":6,\"devices\":[]}\n");goto done; }
    printf("{\"format\":1,\"build\":%lu,\"devices\":[",(unsigned long)os_build());
    for(UINT i=0,printed=0;i<count && i<256;++i) {
        IMMDevice *device=NULL;LPWSTR id=NULL;wchar_t name[4096];
        if(FAILED(IMMDeviceCollection_Item(devices,i,&device)))continue;
        if(SUCCEEDED(IMMDevice_GetId(device,&id))) {
            device_name(device,name);if(printed++)putchar(',');printf("{\"id\":");json_string(id);
            printf(",\"name\":");json_string(name);putchar('}');CoTaskMemFree(id);
        }
        IMMDevice_Release(device);
    }
    printf("]}\n");
done:
    if(devices)IMMDeviceCollection_Release(devices);if(enumerate)IMMDeviceEnumerator_Release(enumerate);
    return FAILED(hr)?CAP_OPEN_FAILED:0;
}
static int validate_process(DWORD pid,uint64_t created,const wchar_t *expected,HANDLE *out) {
    FILETIME born,exited,kernel,user;wchar_t image[32768];DWORD size=32768;
    HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,FALSE,pid);
    if(!process)return 0;
    int ok=WaitForSingleObject(process,0)==WAIT_TIMEOUT && GetProcessTimes(process,&born,&exited,&kernel,&user) &&
        QueryFullProcessImageNameW(process,0,image,&size) &&
        capture_identity_matches(created,filetime_value(born),!_wcsicmp(image,expected));
    if(!ok)CloseHandle(process);else *out=process;return ok;
}
typedef struct { DWORD id,parent;uint64_t born; } Child;
static int process_tree(DWORD root,uint64_t created,DWORD ids[2048]) {
    Child children[2048];unsigned count=0,used=1;ids[0]=root;
    HANDLE snapshot=CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS,0);if(snapshot==INVALID_HANDLE_VALUE)return -1;
    PROCESSENTRY32W entry={0};entry.dwSize=sizeof(entry);
    if(Process32FirstW(snapshot,&entry)) { do {
        if(count<2048)children[count++]=(Child){entry.th32ProcessID,entry.th32ParentProcessID,0};else { CloseHandle(snapshot);return -1; }
    } while(Process32NextW(snapshot,&entry)); }
    CloseHandle(snapshot);
    for(unsigned at=0;at<used;++at)for(unsigned i=0;i<count;++i) {
        if(children[i].parent!=ids[at] || children[i].id==root)continue;
        unsigned j;for(j=0;j<used && ids[j]!=children[i].id;++j) { }if(j<used)continue;
        HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,children[i].id);FILETIME born,exit,kernel,user;
        if(process) {
            if(GetProcessTimes(process,&born,&exit,&kernel,&user) && filetime_value(born)>=created && used<2048)ids[used++]=children[i].id;
            CloseHandle(process);
        }
    }
    return (int)used;
}
static int in_tree(DWORD pid,const DWORD *ids,int count) { for(int i=0;i<count;++i)if(pid==ids[i])return 1;return 0; }
static HRESULT inspect_routes(IMMDeviceEnumerator *enumerate,const wchar_t *wanted,DWORD pid,uint64_t born,CaptureRoutes *out) {
    DWORD ids[2048];int id_count=process_tree(pid,born,ids);if(id_count<0)return E_FAIL;
    IMMDeviceCollection *devices=NULL;UINT count=0;HRESULT hr=IMMDeviceEnumerator_EnumAudioEndpoints(enumerate,eRender,DEVICE_STATE_ACTIVE,&devices);
    memset(out,0,sizeof(*out));if(FAILED(hr))return hr;
    hr=IMMDeviceCollection_GetCount(devices,&count);
    for(UINT i=0;SUCCEEDED(hr) && i<count && i<256;++i) {
        IMMDevice *device=NULL;LPWSTR id=NULL;IAudioSessionManager2 *manager=NULL;IAudioSessionEnumerator *sessions=NULL;
        if(FAILED(IMMDeviceCollection_Item(devices,i,&device)))continue;
        int selected=SUCCEEDED(IMMDevice_GetId(device,&id)) && !wcscmp(id,wanted);
        HRESULT route_hr=IMMDevice_Activate(device,&IID_IAudioSessionManager2,CLSCTX_ALL,NULL,(void **)&manager);
        if(SUCCEEDED(route_hr))route_hr=IAudioSessionManager2_GetSessionEnumerator(manager,&sessions);
        if(SUCCEEDED(route_hr)) {
            int n=0;route_hr=IAudioSessionEnumerator_GetCount(sessions,&n);
            if(SUCCEEDED(route_hr))for(int j=0;j<n && j<4096;++j) {
                IAudioSessionControl *control=NULL;IAudioSessionControl2 *control2=NULL;DWORD session_pid=0;AudioSessionState state=AudioSessionStateExpired;
                if(FAILED(IAudioSessionEnumerator_GetSession(sessions,j,&control)))continue;
                if(SUCCEEDED(IAudioSessionControl_QueryInterface(control,&IID_IAudioSessionControl2,(void **)&control2)) &&
                   SUCCEEDED(IAudioSessionControl2_GetProcessId(control2,&session_pid)) && in_tree(session_pid,ids,id_count) &&
                   SUCCEEDED(IAudioSessionControl_GetState(control,&state))) {
                    if(state==AudioSessionStateActive) { if(selected)++out->selected_active;else ++out->other_active; }
                    else if(state==AudioSessionStateInactive) { if(selected)++out->selected_idle;else ++out->other_idle; }
                }
                if(control2)IAudioSessionControl2_Release(control2);IAudioSessionControl_Release(control);
            }
        }
        if(sessions)IAudioSessionEnumerator_Release(sessions);if(manager)IAudioSessionManager2_Release(manager);
        if(id)CoTaskMemFree(id);IMMDevice_Release(device);
        if(selected && FAILED(route_hr)) { hr=route_hr;break; }
    }
    IMMDeviceCollection_Release(devices);return hr;
}
/* Device/session enumeration can block on drivers. Keep it off the MMCSS capture
 * thread; each worker owns its COM interfaces. Atomics fail closed at a packet
 * boundary, without making network backpressure delay the route checks. */
typedef struct {
    const wchar_t *device_id;DWORD pid;uint64_t born;HANDLE stop,wake;
    volatile LONG code,verified,hresult;
    volatile LONG64 checked_at;
} RouteMonitor;
static RouteMonitor monitor;
static DWORD WINAPI monitor_routes(void *argument) {
    RouteMonitor *self=argument;IMMDeviceEnumerator *enumerate=NULL;IMMDevice *device=NULL;
    HRESULT hr=CoInitializeEx(NULL,COINIT_MULTITHREADED);int initialized=SUCCEEDED(hr),code=CAP_OK;
    if(SUCCEEDED(hr))hr=enumerator(&enumerate);
    if(FAILED(hr))code=CAP_OPEN_FAILED;
    if(!code) { hr=get_device(enumerate,self->device_id,&device);if(FAILED(hr))code=CAP_DEVICE_MISSING; }
    while(!code && WaitForSingleObject(self->stop,250)==WAIT_TIMEOUT) {
        DWORD state=0;CaptureRoutes routes={0};
        hr=IMMDevice_GetState(device,&state);
        if(FAILED(hr) || !(state&DEVICE_STATE_ACTIVE)) { code=CAP_DEVICE_MISSING;break; }
        hr=inspect_routes(enumerate,self->device_id,self->pid,self->born,&routes);
        if(FAILED(hr)) { code=CAP_OPEN_FAILED;break; }
        code=capture_route_error(routes);
        InterlockedExchange(&self->verified,capture_route_verified(routes));
        InterlockedExchange64(&self->checked_at,(LONG64)GetTickCount64());
    }
    if(code) {
        InterlockedExchange(&self->verified,0);InterlockedExchange(&self->hresult,(LONG)hr);
        InterlockedExchange(&self->code,code);SetEvent(self->wake);
    }
    if(device)IMMDevice_Release(device);if(enumerate)IMMDeviceEnumerator_Release(enumerate);
    if(initialized)CoUninitialize();CloseHandle(self->wake);return 0;
}
typedef struct {
    IActivateAudioInterfaceCompletionHandler iface;LONG refs;HANDLE event;HRESULT result;
    IAudioClient *client;IUnknown *marshaler;
} Activation;
static Activation activation;
static HRESULT STDMETHODCALLTYPE activate_query(IActivateAudioInterfaceCompletionHandler *iface,REFIID iid,void **out) {
    Activation *self=(Activation *)iface;*out=NULL;
    if(IsEqualIID(iid,&IID_IUnknown) || IsEqualIID(iid,&IID_IAgileObject) || IsEqualIID(iid,&IID_IActivateAudioInterfaceCompletionHandler)) {
        *out=iface;InterlockedIncrement(&self->refs);return S_OK;
    }
    if(self->marshaler)return IUnknown_QueryInterface(self->marshaler,iid,out);
    return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE activate_addref(IActivateAudioInterfaceCompletionHandler *iface) { return (ULONG)InterlockedIncrement(&((Activation *)iface)->refs); }
static ULONG STDMETHODCALLTYPE activate_release(IActivateAudioInterfaceCompletionHandler *iface) { return (ULONG)InterlockedDecrement(&((Activation *)iface)->refs); }
static HRESULT STDMETHODCALLTYPE activate_complete(IActivateAudioInterfaceCompletionHandler *iface,IActivateAudioInterfaceAsyncOperation *operation) {
    Activation *self=(Activation *)iface;IUnknown *object=NULL;HRESULT result=E_FAIL;
    HRESULT hr=IActivateAudioInterfaceAsyncOperation_GetActivateResult(operation,&result,&object);
    if(SUCCEEDED(hr))hr=result;
    if(SUCCEEDED(hr))hr=IUnknown_QueryInterface(object,&IID_IAudioClient,(void **)&self->client);
    if(object)IUnknown_Release(object);self->result=hr;SetEvent(self->event);return S_OK;
}
static IActivateAudioInterfaceCompletionHandlerVtbl activation_vtable={activate_query,activate_addref,activate_release,activate_complete};
static HRESULT activate_capture(DWORD pid,IAudioClient **client) {
    activation.iface.lpVtbl=&activation_vtable;activation.refs=1;activation.result=E_FAIL;
    activation.event=CreateEventW(NULL,FALSE,FALSE,NULL);if(!activation.event)return E_FAIL;
    HRESULT hr=CoCreateFreeThreadedMarshaler((IUnknown *)&activation.iface,&activation.marshaler);
    if(FAILED(hr))return hr;
    ActivationParams params={0};params.type=1;params.process.target=pid;params.process.mode=0;
    PROPVARIANT value;PropVariantInit(&value);value.vt=VT_BLOB;value.blob.cbSize=sizeof(params);value.blob.pBlobData=(BYTE *)&params;
    IActivateAudioInterfaceAsyncOperation *operation=NULL;
    hr=ActivateAudioInterfaceAsync(L"VAD\\Process_Loopback",&IID_IAudioClient,&value,&activation.iface,&operation);
    if(SUCCEEDED(hr)) {
        if(WaitForSingleObject(activation.event,5000)!=WAIT_OBJECT_0)hr=HRESULT_FROM_WIN32(ERROR_TIMEOUT);
        else { hr=activation.result;if(SUCCEEDED(hr))*client=activation.client; }
    }
    if(operation)IActivateAudioInterfaceAsyncOperation_Release(operation);
    /* On timeout the static callback remains alive until process exit. */
    return hr;
}
static int probe_or_capture(const wchar_t *device_id,DWORD pid,uint64_t born,const wchar_t *exe,int capture,int prepare) {
    IMMDeviceEnumerator *enumerate=NULL;IMMDevice *device=NULL;HANDLE process=NULL;IAudioClient *client=NULL;
    IAudioCaptureClient *recorder=NULL;HRESULT hr=S_OK;int code=CAP_OK,ready=0;CaptureRoutes routes={0};
    wchar_t name[4096]=L"";DWORD task=0;HANDLE priority=NULL;
    HANDLE route_thread=NULL;
    if(os_build()<20348) { code=CAP_UNSUPPORTED;goto done; }
    hr=enumerator(&enumerate);if(FAILED(hr)) { code=CAP_OPEN_FAILED;goto done; }
    hr=get_device(enumerate,device_id,&device);if(FAILED(hr)) { code=CAP_DEVICE_MISSING;goto done; }
    device_name(device,name);
    if(prepare) {
        IAudioEndpointVolume *volume=NULL;
        hr=IMMDevice_Activate(device,&IID_IAudioEndpointVolume,CLSCTX_ALL,NULL,(void **)&volume);
        if(SUCCEEDED(hr))hr=IAudioEndpointVolume_SetMasterVolumeLevelScalar(volume,1.0f,NULL);
        if(SUCCEEDED(hr))hr=IAudioEndpointVolume_SetMute(volume,FALSE,NULL);
        if(volume)IAudioEndpointVolume_Release(volume);if(FAILED(hr))code=CAP_OPEN_FAILED;goto done;
    }
    if(!validate_process(pid,born,exe,&process)) { code=CAP_PROCESS_MISSING;goto done; }
    hr=inspect_routes(enumerate,device_id,pid,born,&routes);if(FAILED(hr)) { code=CAP_OPEN_FAILED;goto done; }
    code=capture_route_error(routes);if(code || !capture)goto done;
    hr=activate_capture(pid,&client);if(FAILED(hr)) { code=CAP_OPEN_FAILED;goto done; }
    WAVEFORMATEX format={WAVE_FORMAT_PCM,2,48000,192000,4,16,0};
    hr=IAudioClient_Initialize(client,AUDCLNT_SHAREMODE_SHARED,AUDCLNT_STREAMFLAGS_LOOPBACK|AUDCLNT_STREAMFLAGS_EVENTCALLBACK|
        AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM|AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY,0,0,&format,NULL);
    if(SUCCEEDED(hr))hr=IAudioClient_GetService(client,&IID_IAudioCaptureClient,(void **)&recorder);
    audio_event=CreateEventW(NULL,FALSE,FALSE,NULL);
    if(SUCCEEDED(hr) && !audio_event)hr=E_FAIL;
    if(SUCCEEDED(hr))hr=IAudioClient_SetEventHandle(client,audio_event);
    if(SUCCEEDED(hr))hr=IAudioClient_Start(client);
    if(FAILED(hr)) { code=CAP_OPEN_FAILED;goto done; }
    monitor.device_id=device_id;monitor.pid=pid;monitor.born=born;
    monitor.code=0;monitor.hresult=0;monitor.verified=capture_route_verified(routes);
    monitor.checked_at=(LONG64)GetTickCount64();monitor.wake=NULL;
    monitor.stop=CreateEventW(NULL,TRUE,FALSE,NULL);
    if(monitor.stop && DuplicateHandle(GetCurrentProcess(),audio_event,GetCurrentProcess(),&monitor.wake,0,FALSE,DUPLICATE_SAME_ACCESS))
        route_thread=CreateThread(NULL,0,monitor_routes,&monitor,0,NULL);
    if(!route_thread) { code=CAP_OPEN_FAILED;hr=HRESULT_FROM_WIN32(GetLastError());goto done; }
    startup(0,S_OK);ready=1;priority=AvSetMmThreadCharacteristicsW(L"Audio",&task);
    unsigned discontinuities=0;HANDLE waits[2]={audio_event,process};
    static BYTE silence[48000*4];
    while(!stopping) {
        DWORD result=WaitForMultipleObjects(2,waits,FALSE,250);
        if(result==WAIT_OBJECT_0+1 || WaitForSingleObject(process,0)!=WAIT_TIMEOUT) { code=CAP_PROCESS_MISSING;break; }
        if(result!=WAIT_OBJECT_0 && result!=WAIT_TIMEOUT) { code=CAP_OPEN_FAILED;break; }
        code=(int)InterlockedCompareExchange(&monitor.code,0,0);
        if(code) { hr=(HRESULT)InterlockedCompareExchange(&monitor.hresult,0,0);break; }
        if(GetTickCount64()-(uint64_t)InterlockedCompareExchange64(&monitor.checked_at,0,0)>3000) {
            code=CAP_OPEN_FAILED;hr=HRESULT_FROM_WIN32(ERROR_TIMEOUT);break;
        }
        UINT32 frames=0;hr=IAudioCaptureClient_GetNextPacketSize(recorder,&frames);
        while(SUCCEEDED(hr) && frames && !stopping) {
            BYTE *data=NULL;DWORD flags=0;UINT64 position=0,timestamp=0;
            hr=IAudioCaptureClient_GetBuffer(recorder,&data,&frames,&flags,&position,&timestamp);if(FAILED(hr))break;
            int valid=frames<=48000;
            const BYTE *samples=(flags&AUDCLNT_BUFFERFLAGS_SILENT) || !InterlockedCompareExchange(&monitor.verified,0,0)?silence:data;
            if(flags&AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY) {
                fprintf(stderr,"{\"event\":\"discontinuity\",\"count\":%u}\n",++discontinuities);fflush(stderr);
            }
            int written=valid && samples && write_bytes(samples,(size_t)frames*4);
            HRESULT release=IAudioCaptureClient_ReleaseBuffer(recorder,frames);
            if(!written || FAILED(release)) { InterlockedExchange(&stopping,1);break; }
            hr=IAudioCaptureClient_GetNextPacketSize(recorder,&frames);
        }
        if(FAILED(hr)) { code=CAP_OPEN_FAILED;break; }
    }
done:
    if(monitor.stop)SetEvent(monitor.stop);
    if(route_thread) {
        /* A stuck driver must not hold up shutdown. Context/event remain valid
         * until process exit if its COM call has not returned in one second. */
        if(WaitForSingleObject(route_thread,1000)==WAIT_OBJECT_0) { CloseHandle(monitor.stop);monitor.stop=NULL; }
        CloseHandle(route_thread);
    } else {
        if(monitor.stop) { CloseHandle(monitor.stop);monitor.stop=NULL; }
        if(monitor.wake) { CloseHandle(monitor.wake);monitor.wake=NULL; }
    }
    if(code)report_error(code,hr);
    if(capture && !ready)startup(code,hr);
    if(!capture) {
        printf("{\"format\":1,\"code\":%d,\"hresult\":%lu,\"device_name\":",code,(unsigned long)hr);json_string(name);
        printf(",\"route_verified\":%s,\"selected_active\":%u,\"other_active\":%u,\"selected_idle\":%u,\"other_idle\":%u}\n",
            capture_route_verified(routes)?"true":"false",routes.selected_active,routes.other_active,routes.selected_idle,routes.other_idle);
    }
    if(client)IAudioClient_Stop(client);if(priority)AvRevertMmThreadCharacteristics(priority);
    if(recorder)IAudioCaptureClient_Release(recorder);if(client)IAudioClient_Release(client);
    if(audio_event) { CloseHandle(audio_event);audio_event=NULL; }
    if(process)CloseHandle(process);if(device)IMMDevice_Release(device);if(enumerate)IMMDeviceEnumerator_Release(enumerate);
    return code;
}
static int number(const wchar_t *s,uint64_t *out) {
    if(!s || !*s || wcslen(s)>20)return 0;for(const wchar_t *p=s;*p;++p)if(*p<L'0' || *p>L'9')return 0;
    wchar_t *end=NULL;errno=0;unsigned long long value=wcstoull(s,&end,10);
    if(errno || !end || *end)return 0;*out=(uint64_t)value;return 1;
}
int wmain(int argc,wchar_t **argv) {
    if(argc==2 && !wcscmp(argv[1],L"--version")) { printf("Vita Soloist Capture %s\n",VERSION);return 0; }
    if(argc==2 && !wcscmp(argv[1],L"--info")) { printf("{\"format\":1,\"build\":%lu,\"minimum_build\":20348}\n",(unsigned long)os_build());return 0; }
    int capture=0,probe=0,list=0,prepare=0;const wchar_t *device=NULL,*exe=NULL;uint64_t pid=0,born=0;
    for(int i=1;i<argc;++i) {
        if(!wcscmp(argv[i],L"--capture"))capture=1;
        else if(!wcscmp(argv[i],L"--probe"))probe=1;
        else if(!wcscmp(argv[i],L"--list-devices"))list=1;
        else if(!wcscmp(argv[i],L"--prepare-device"))prepare=1;
        else if(!wcscmp(argv[i],L"--device") && i+1<argc)device=argv[++i];
        else if(!wcscmp(argv[i],L"--exe") && i+1<argc)exe=argv[++i];
        else if(!wcscmp(argv[i],L"--pid") && i+1<argc && number(argv[i+1],&pid))++i;
        else if(!wcscmp(argv[i],L"--created") && i+1<argc && number(argv[i+1],&born))++i;
        else { fprintf(stderr,"Invalid capture helper arguments\n");return 64; }
    }
    if(capture+probe+list+prepare!=1 || (!list && (!device || wcslen(device)>2048)) ||
       ((capture || probe) && (!pid || pid>0xffffffffu || !born || !exe || wcslen(exe)>32760)))return 64;
    HRESULT hr=CoInitializeEx(NULL,COINIT_MULTITHREADED);if(FAILED(hr))return CAP_OPEN_FAILED;
    SetConsoleCtrlHandler(console_stop,TRUE);
    int result=list?list_devices():probe_or_capture(device,(DWORD)pid,born,exe,capture,prepare);
    CoUninitialize();return result;
}
