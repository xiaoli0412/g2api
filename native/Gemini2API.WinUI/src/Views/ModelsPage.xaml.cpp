#include "pch.h"
#include "ModelsPage.xaml.h"
#include "PageContent.h"

#if __has_include("Views.ModelsPage.g.cpp")
#include "Views.ModelsPage.g.cpp"
#endif

namespace winrt::Gemini2API::Views::implementation
{
    ModelsPage::ModelsPage()
    {
        Content(BuildPage(
            L"Models",
            L"Model catalog exposed through /v1/models",
            L"Source",
            L"Backend model registry",
            L"Compatibility",
            L"OpenAI model list shape",
            L"Refresh",
            L"Resolved from local service"));
    }
}
