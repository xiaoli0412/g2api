#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <string>

namespace Gemini2API
{
    class BackendProcess
    {
    public:
        BackendProcess() = default;
        ~BackendProcess();

        BackendProcess(BackendProcess const&) = delete;
        BackendProcess& operator=(BackendProcess const&) = delete;

        bool Start(
            const std::wstring& pythonExe,
            const std::wstring& configPath,
            unsigned short port,
            const std::wstring& workingDirectory = {},
            const std::wstring& supervisorExe = {});

        void Stop();
        bool IsRunning() const;
        bool IsUsingSupervisor() const;
        unsigned long ProcessId() const;

    private:
        void CloseHandles();
        bool StartCommand(
            std::wstring const& commandLine,
            std::wstring const& workingDirectory,
            HANDLE stdoutWrite,
            HANDLE stderrWrite);

        HANDLE m_jobHandle = nullptr;
        HANDLE m_processHandle = nullptr;
        HANDLE m_threadHandle = nullptr;
        HANDLE m_stdoutRead = nullptr;
        HANDLE m_stderrRead = nullptr;
        unsigned long m_processId = 0;
        bool m_usingSupervisor = false;
    };
}
