#pragma once

#include "Views.CookiesPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct CookiesPage : CookiesPageT<CookiesPage>
    {
        CookiesPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct CookiesPage : CookiesPageT<CookiesPage, implementation::CookiesPage>
    {
    };
}
