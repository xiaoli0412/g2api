#pragma once

#include "Views.ModelsPage.g.h"

namespace winrt::Gemini2API::Views::implementation
{
    struct ModelsPage : ModelsPageT<ModelsPage>
    {
        ModelsPage();
    };
}

namespace winrt::Gemini2API::Views::factory_implementation
{
    struct ModelsPage : ModelsPageT<ModelsPage, implementation::ModelsPage>
    {
    };
}
