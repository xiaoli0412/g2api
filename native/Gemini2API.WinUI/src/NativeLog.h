#pragma once

#include <cwchar>
#include <string>

namespace Gemini2API
{
    inline std::wstring RuntimeLogPath()
    {
        wchar_t tempPath[MAX_PATH]{};
        auto length = GetTempPathW(MAX_PATH, tempPath);
        if (length == 0 || length >= MAX_PATH) {
            return L"Gemini2API.WinUI.runtime.log";
        }

        return std::wstring(tempPath) + L"Gemini2API.WinUI.runtime.log";
    }

    inline void WriteRuntimeLog(std::wstring const& message)
    {
        auto path = RuntimeLogPath();
        auto file = CreateFileW(
            path.c_str(),
            FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr,
            OPEN_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            nullptr);

        if (file == INVALID_HANDLE_VALUE) {
            return;
        }

        auto line = message + L"\r\n";
        DWORD written = 0;
        WriteFile(file, line.data(), static_cast<DWORD>(line.size() * sizeof(wchar_t)), &written, nullptr);
        CloseHandle(file);
    }

    inline void WriteRuntimeLog(wchar_t const* message)
    {
        WriteRuntimeLog(std::wstring(message));
    }

    inline void WriteRuntimeLog(char const* message)
    {
        auto length = MultiByteToWideChar(CP_UTF8, 0, message, -1, nullptr, 0);
        if (length <= 0) {
            WriteRuntimeLog(L"<non-unicode runtime error>");
            return;
        }

        std::wstring wide(static_cast<size_t>(length), L'\0');
        MultiByteToWideChar(CP_UTF8, 0, message, -1, wide.data(), length);
        if (!wide.empty() && wide.back() == L'\0') {
            wide.pop_back();
        }
        WriteRuntimeLog(wide);
    }
}
