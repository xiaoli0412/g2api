#pragma once

#include "Views.StreamingPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct StreamingPage : StreamingPageT<StreamingPage>
    {
        StreamingPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct StreamingPage : StreamingPageT<StreamingPage, implementation::StreamingPage>
    {
    };
}
