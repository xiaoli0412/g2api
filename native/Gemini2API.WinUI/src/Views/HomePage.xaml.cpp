#include "pch.h"
#include "HomePage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.HomePage.g.cpp")
#include "Views.HomePage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    HomePage::HomePage()
    {
        Content(BuildPage(
            L"Overview",
            L"Service health and native shell summary",
            L"Runtime",
            L"Windows App SDK with WinUI 3",
            L"Backdrop",
            L"Mica with Acrylic fallback",
            L"Backend",
            L"Existing Gemini2API Python server"));
    }
}
