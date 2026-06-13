#include "pch.h"
#include "BackendClient.h"

#include <Windows.h>
#include <winhttp.h>

#include <algorithm>
#include <chrono>
#include <sstream>
#include <utility>
#include <vector>

#pragma comment(lib, "winhttp.lib")

namespace Gemini2API
{
    namespace
    {
        constexpr auto kCacheTtl = std::chrono::milliseconds(900);
        constexpr int kResolveTimeoutMs = 120;
        constexpr int kConnectTimeoutMs = 180;
        constexpr int kSendTimeoutMs = 250;
        constexpr int kReceiveTimeoutMs = 450;

        std::wstring JoinUrl(std::wstring baseUrl, std::wstring const& path)
        {
            while (!baseUrl.empty() && baseUrl.back() == L'/')
            {
                baseUrl.pop_back();
            }

            if (path.empty() || path.front() == L'/')
            {
                return baseUrl + path;
            }

            return baseUrl + L"/" + path;
        }

        std::wstring Utf8ToWide(std::string const& value)
        {
            if (value.empty())
            {
                return {};
            }

            int size = MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0);
            if (size <= 0)
            {
                return {};
            }

            std::wstring result(static_cast<size_t>(size), L'\0');
            MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), size);
            return result;
        }

        std::wstring LastErrorMessage(DWORD errorCode)
        {
            wchar_t* buffer = nullptr;
            DWORD size = FormatMessageW(
                FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                nullptr,
                errorCode,
                MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
                reinterpret_cast<LPWSTR>(&buffer),
                0,
                nullptr);

            std::wstring message = size > 0 && buffer ? std::wstring(buffer, size) : L"Unknown WinHTTP error";
            if (buffer)
            {
                LocalFree(buffer);
            }

            while (!message.empty() && (message.back() == L'\r' || message.back() == L'\n'))
            {
                message.pop_back();
            }
            return message;
        }
    }

    BackendClient::BackendClient(std::wstring baseUrl) : m_baseUrl(std::move(baseUrl)) {}

    BackendStatus BackendClient::GetStatus() const
    {
        auto now = std::chrono::steady_clock::now();
        if (m_statusCacheAt.time_since_epoch().count() != 0 && now - m_statusCacheAt < kCacheTtl)
        {
            return m_statusCache;
        }

        BackendStatus status;
        status.baseUrl = m_baseUrl;
        auto response = Get(L"/");
        status.reachable = response.ok;
        status.httpStatus = response.statusCode;

        if (response.ok)
        {
            status.version = TryReadJsonString(response.body, L"version").value_or(L"unknown");
        }
        else
        {
            status.error = response.error;
        }

        m_statusCache = status;
        m_statusCacheAt = now;
        return status;
    }

    std::wstring BackendClient::GetModelsJson() const
    {
        auto response = Get(L"/v1/models");
        return response.ok ? response.body : L"{}";
    }

    std::wstring BackendClient::GetAdminStatsJson() const
    {
        auto now = std::chrono::steady_clock::now();
        if (!m_adminStatsCache.empty() && now - m_adminStatsCacheAt < kCacheTtl)
        {
            return m_adminStatsCache;
        }

        auto response = Get(L"/admin/stats");
        m_adminStatsCache = response.ok ? response.body : L"{}";
        m_adminStatsCacheAt = now;
        return m_adminStatsCache;
    }

    HttpResponse BackendClient::Get(std::wstring path) const
    {
        HttpResponse result;
        std::wstring url = JoinUrl(m_baseUrl, path);

        URL_COMPONENTS components{};
        components.dwStructSize = sizeof(components);
        components.dwSchemeLength = static_cast<DWORD>(-1);
        components.dwHostNameLength = static_cast<DWORD>(-1);
        components.dwUrlPathLength = static_cast<DWORD>(-1);
        components.dwExtraInfoLength = static_cast<DWORD>(-1);

        if (!WinHttpCrackUrl(url.c_str(), static_cast<DWORD>(url.size()), 0, &components))
        {
            result.error = L"Invalid URL: " + url;
            return result;
        }

        std::wstring host(components.lpszHostName, components.dwHostNameLength);
        std::wstring objectPath(components.lpszUrlPath, components.dwUrlPathLength);
        if (components.dwExtraInfoLength > 0)
        {
            objectPath.append(components.lpszExtraInfo, components.dwExtraInfoLength);
        }
        if (objectPath.empty())
        {
            objectPath = L"/";
        }

        HINTERNET session = WinHttpOpen(
            L"Gemini2API.WinUI/0.1",
            WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
            WINHTTP_NO_PROXY_NAME,
            WINHTTP_NO_PROXY_BYPASS,
            0);
        if (!session)
        {
            result.error = LastErrorMessage(GetLastError());
            return result;
        }
        WinHttpSetTimeouts(session, kResolveTimeoutMs, kConnectTimeoutMs, kSendTimeoutMs, kReceiveTimeoutMs);

        HINTERNET connection = WinHttpConnect(session, host.c_str(), components.nPort, 0);
        if (!connection)
        {
            result.error = LastErrorMessage(GetLastError());
            WinHttpCloseHandle(session);
            return result;
        }

        DWORD flags = components.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
        HINTERNET request = WinHttpOpenRequest(
            connection,
            L"GET",
            objectPath.c_str(),
            nullptr,
            WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES,
            flags);
        if (!request)
        {
            result.error = LastErrorMessage(GetLastError());
            WinHttpCloseHandle(connection);
            WinHttpCloseHandle(session);
            return result;
        }

        bool sent = WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0);
        bool received = sent && WinHttpReceiveResponse(request, nullptr);
        if (!received)
        {
            result.error = LastErrorMessage(GetLastError());
            WinHttpCloseHandle(request);
            WinHttpCloseHandle(connection);
            WinHttpCloseHandle(session);
            return result;
        }

        DWORD statusCode = 0;
        DWORD statusCodeSize = sizeof(statusCode);
        WinHttpQueryHeaders(
            request,
            WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
            WINHTTP_HEADER_NAME_BY_INDEX,
            &statusCode,
            &statusCodeSize,
            WINHTTP_NO_HEADER_INDEX);
        result.statusCode = statusCode;

        std::string bytes;
        DWORD available = 0;
        while (WinHttpQueryDataAvailable(request, &available) && available > 0)
        {
            std::vector<char> buffer(available);
            DWORD read = 0;
            if (!WinHttpReadData(request, buffer.data(), available, &read) || read == 0)
            {
                break;
            }
            bytes.append(buffer.data(), buffer.data() + read);
        }

        result.body = Utf8ToWide(bytes);
        result.ok = statusCode >= 200 && statusCode < 300;
        if (!result.ok)
        {
            std::wstringstream stream;
            stream << L"HTTP " << statusCode << L" from " << url;
            result.error = stream.str();
        }

        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return result;
    }

    std::optional<std::wstring> BackendClient::TryReadJsonString(std::wstring const& json, std::wstring const& key) const
    {
        std::wstring pattern = L"\"" + key + L"\"";
        size_t keyIndex = json.find(pattern);
        if (keyIndex == std::wstring::npos)
        {
            return std::nullopt;
        }

        size_t colon = json.find(L':', keyIndex + pattern.size());
        if (colon == std::wstring::npos)
        {
            return std::nullopt;
        }

        size_t firstQuote = json.find(L'"', colon + 1);
        if (firstQuote == std::wstring::npos)
        {
            return std::nullopt;
        }

        size_t secondQuote = json.find(L'"', firstQuote + 1);
        if (secondQuote == std::wstring::npos || secondQuote <= firstQuote)
        {
            return std::nullopt;
        }

        return json.substr(firstQuote + 1, secondQuote - firstQuote - 1);
    }
}
