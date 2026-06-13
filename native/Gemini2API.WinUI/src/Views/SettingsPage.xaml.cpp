#include "pch.h"
#include "SettingsPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.SettingsPage.g.cpp")
#include "Views.SettingsPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    SettingsPage::SettingsPage()
    {
        Content(BuildPage(
            L"Settings",
            L"Native shell preferences",
            L"Language",
            L"English Windows system-app tone",
            L"Material",
            L"Mica, Acrylic flyouts, no gradients",
            L"Layout",
            L"48 px compact navigation rail"));
    }
}
