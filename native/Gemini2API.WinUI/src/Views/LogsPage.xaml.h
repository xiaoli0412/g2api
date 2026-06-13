#pragma once

#include "Views.LogsPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct LogsPage : LogsPageT<LogsPage>
    {
        LogsPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct LogsPage : LogsPageT<LogsPage, implementation::LogsPage>
    {
    };
}
