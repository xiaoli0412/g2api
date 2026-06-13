#pragma once

#include "Views.ServerPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct ServerPage : ServerPageT<ServerPage>
    {
        ServerPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct ServerPage : ServerPageT<ServerPage, implementation::ServerPage>
    {
    };
}
