#include "pch.h"
#include "App.xaml.h"
#include "MainWindow.xaml.h"
#include "NativeLog.h"

#if __has_include("App.g.cpp")
#include "App.g.cpp"
#endif

namespace winrt::Gemini2API::implementation
{
    App::App()
    {
        ::Gemini2API::WriteRuntimeLog(L"App: constructing");
        ::Gemini2API::WriteRuntimeLog(L"App: setting requested theme");
        RequestedTheme(Microsoft::UI::Xaml::ApplicationTheme::Dark);
        ::Gemini2API::WriteRuntimeLog(L"App: requested theme set");
        ::Gemini2API::WriteRuntimeLog(L"App: resources are provided by native code");
    }

    void App::OnLaunched(Microsoft::UI::Xaml::LaunchActivatedEventArgs const&)
    {
        ::Gemini2API::WriteRuntimeLog(L"App: OnLaunched");
        try
        {
            ::Gemini2API::WriteRuntimeLog(L"App: creating MainWindow");
            m_window = winrt::make<Gemini2API::implementation::MainWindow>();
            ::Gemini2API::WriteRuntimeLog(L"App: activating MainWindow");
            m_window.Activate();
            ::Gemini2API::WriteRuntimeLog(L"App: MainWindow activated");
        }
        catch (winrt::hresult_error const& ex)
        {
            ::Gemini2API::WriteRuntimeLog(std::wstring(L"App: hresult_error: ") + ex.message().c_str());
            throw;
        }
        catch (std::exception const& ex)
        {
            ::Gemini2API::WriteRuntimeLog("App: std::exception");
            ::Gemini2API::WriteRuntimeLog(ex.what());
            throw;
        }
    }
}
