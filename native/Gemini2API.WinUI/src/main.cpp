#include "pch.h"
#include "App.xaml.h"
#include "NativeLog.h"

#include <WindowsAppSDK-VersionInfo.h>
#include <MddBootstrap.h>

using namespace winrt;
namespace MddBootstrap = ::Microsoft::Windows::ApplicationModel::DynamicDependency::Bootstrap;

namespace
{
    void ConfigureDpiAwareness()
    {
        if (SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        {
            ::Gemini2API::WriteRuntimeLog(L"main: DPI awareness set to PerMonitorV2");
            return;
        }

        SetProcessDPIAware();
        ::Gemini2API::WriteRuntimeLog(L"main: DPI awareness fallback set to system aware");
    }
}

int __stdcall wWinMain(HINSTANCE, HINSTANCE, PWSTR, int)
{
    try
    {
        ConfigureDpiAwareness();

        ::Gemini2API::WriteRuntimeLog(L"main: bootstrap start");
        auto bootstrapCleanup = MddBootstrap::Initialize(
            WINDOWSAPPSDK_RELEASE_MAJORMINOR,
            WINDOWSAPPSDK_RELEASE_VERSION_TAG_W,
            WINDOWSAPPSDK_RUNTIME_VERSION_UINT64,
            MddBootstrap::InitializeOptions::OnNoMatch_ShowUI);
        ::Gemini2API::WriteRuntimeLog(L"main: bootstrap complete");

        init_apartment(apartment_type::single_threaded);
        ::Gemini2API::WriteRuntimeLog(L"main: apartment initialized");

        winrt::Microsoft::UI::Xaml::Application::Start([](auto&&)
        {
            ::Gemini2API::WriteRuntimeLog(L"main: Application::Start factory");
            make<winrt::Gemini2API::implementation::App>();
        });
        ::Gemini2API::WriteRuntimeLog(L"main: Application::Start returned");
    }
    catch (winrt::hresult_error const& ex)
    {
        ::Gemini2API::WriteRuntimeLog(std::wstring(L"main: hresult_error: ") + ex.message().c_str());
        return ex.code();
    }
    catch (std::exception const& ex)
    {
        ::Gemini2API::WriteRuntimeLog("main: std::exception");
        ::Gemini2API::WriteRuntimeLog(ex.what());
        return -1;
    }

    return 0;
}
