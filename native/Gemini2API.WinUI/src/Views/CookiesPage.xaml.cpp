#include "pch.h"
#include "CookiesPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.CookiesPage.g.cpp")
#include "Views.CookiesPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    CookiesPage::CookiesPage()
    {
        Content(BuildPage(
            L"Cookies",
            L"Authentication inventory and diagnostics",
            L"Storage",
            L"Backend-managed cookie sets",
            L"Validation",
            L"Admin cookie endpoints",
            L"Privacy",
            L"Local-only management surface"));
    }
}
