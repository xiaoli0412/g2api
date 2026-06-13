#pragma once

#include "Views.HomePage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct HomePage : HomePageT<HomePage>
    {
        HomePage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct HomePage : HomePageT<HomePage, implementation::HomePage>
    {
    };
}
