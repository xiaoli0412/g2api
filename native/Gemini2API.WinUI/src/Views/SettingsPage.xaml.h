#pragma once

#include "Views.SettingsPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct SettingsPage : SettingsPageT<SettingsPage>
    {
        SettingsPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct SettingsPage : SettingsPageT<SettingsPage, implementation::SettingsPage>
    {
    };
}
