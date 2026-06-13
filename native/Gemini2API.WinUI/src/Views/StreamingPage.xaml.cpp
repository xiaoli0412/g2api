#include "pch.h"
#include "StreamingPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.StreamingPage.g.cpp")
#include "Views.StreamingPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    StreamingPage::StreamingPage()
    {
        Content(BuildPage(
            L"Streaming",
            L"SSE and response pipeline status",
            L"Protocol",
            L"OpenAI-compatible streaming",
            L"Transport",
            L"Local HTTP bridge",
            L"Diagnostics",
            L"Response timing and stream health"));
    }
}
