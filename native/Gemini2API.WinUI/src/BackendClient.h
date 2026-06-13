#pragma once

#include <optional>
#include <string>
#include <chrono>

namespace Gemini2API
{
    struct HttpResponse
    {
        bool ok = false;
        unsigned long statusCode = 0;
        std::wstring body;
        std::wstring error;
    };

    struct BackendStatus
    {
        bool reachable = false;
        unsigned long httpStatus = 0;
        std::wstring version;
        std::wstring baseUrl;
        std::wstring error;
    };

    class BackendClient
    {
    public:
        explicit BackendClient(std::wstring baseUrl);

        BackendStatus GetStatus() const;
        std::wstring GetModelsJson() const;
        std::wstring GetAdminStatsJson() const;

    private:
        HttpResponse Get(std::wstring path) const;
        std::optional<std::wstring> TryReadJsonString(std::wstring const& json, std::wstring const& key) const;

        std::wstring m_baseUrl;
        mutable BackendStatus m_statusCache;
        mutable std::chrono::steady_clock::time_point m_statusCacheAt{};
        mutable std::wstring m_adminStatsCache;
        mutable std::chrono::steady_clock::time_point m_adminStatsCacheAt{};
    };
}
