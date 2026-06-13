#include "pch.h"
#include "ServerPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.ServerPage.g.cpp")
#include "Views.ServerPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    ServerPage::ServerPage()
    {
        Content(BuildPage(
            L"Server",
            L"Local API process control",
            L"Command",
            L"python -m gemini_web2api",
            L"Default endpoint",
            L"http://127.0.0.1:18081",
            L"Mode",
            L"Unpackaged native supervisor shell"));
    }
}
