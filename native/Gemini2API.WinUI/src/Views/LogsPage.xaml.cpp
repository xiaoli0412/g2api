#include "pch.h"
#include "LogsPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.LogsPage.g.cpp")
#include "Views.LogsPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    LogsPage::LogsPage()
    {
        Content(BuildPage(
            L"Logs",
            L"Process output and operational events",
            L"Channels",
            L"Backend stdout and stderr",
            L"Format",
            L"Timestamped local records",
            L"Retention",
            L"Session-scoped native shell view"));
    }
}
