#pragma once

#include "App.g.h"

namespace winrt::Gemini2API::implementation
{
    struct App : AppT<App>
    {
        App();

        void OnLaunched(Microsoft::UI::Xaml::LaunchActivatedEventArgs const& args);

    private:
        Microsoft::UI::Xaml::Window m_window{ nullptr };
    };
}

namespace winrt::Gemini2API::factory_implementation
{
    struct App : AppT<App, implementation::App>
    {
    };
}
