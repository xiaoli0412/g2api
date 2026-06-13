#pragma once

#include "BackendClient.h"
#include "BackendProcess.h"
#include "MainWindow.g.h"

#include <atomic>

namespace winrt::Gemini2API::implementation
{
    struct MainWindow : MainWindowT<MainWindow>
    {
        MainWindow();

        void RootNavigation_SelectionChanged(
            Microsoft::UI::Xaml::Controls::NavigationView const& sender,
            Microsoft::UI::Xaml::Controls::NavigationViewSelectionChangedEventArgs const& args);

    private:
        void BuildLayout();
        void ApplySystemBackdrop();
        void StartLiveRefresh();
        void StartBackendService();
        void StopBackendService();
        void OpenDashboard();
        void NavigateTo(winrt::hstring const& tag, bool allowBackendRefresh = true);
        void QueueBackendRefresh(winrt::hstring const& tag);
        void SetBackendStatus(winrt::hstring const& text, bool running);
        void ToggleLanguage();
        void UpdateShellText();
        void UpdateNavigationState();
        winrt::hstring Text(wchar_t const* key) const;

        Microsoft::UI::Xaml::Controls::StackPanel m_contentPanel{ nullptr };
        Microsoft::UI::Xaml::Controls::NavigationView m_rootNavigation{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock m_backendStatusText{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock m_titleText{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock m_subtitleText{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock m_languageText{ nullptr };
        Microsoft::UI::Xaml::Controls::Grid m_appTitleBar{ nullptr };
        Microsoft::UI::Xaml::Shapes::Ellipse m_backendStatusDot{ nullptr };
        Microsoft::UI::Dispatching::DispatcherQueueTimer m_liveRefreshTimer{ nullptr };
        std::vector<Microsoft::UI::Xaml::Controls::Border> m_navItems;
        std::vector<winrt::hstring> m_navTags;
        winrt::hstring m_currentTag{ L"home" };
        bool m_useChinese{ false };
        std::wstring m_cachedStatsJson{ L"{}" };
        ::Gemini2API::BackendStatus m_cachedStatus;
        std::atomic<uint64_t> m_backendRefreshVersion{ 0 };
        std::atomic_bool m_backendRefreshInFlight{ false };

        ::Gemini2API::BackendProcess m_backendProcess;
        ::Gemini2API::BackendClient m_backendClient{ L"http://127.0.0.1:18081" };
    };
}

namespace winrt::Gemini2API::factory_implementation
{
    struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
    {
    };
}
