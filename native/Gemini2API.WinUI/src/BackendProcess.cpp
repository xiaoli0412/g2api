#include "pch.h"
#include "BackendProcess.h"

#include <sstream>
#include <TlHelp32.h>
#include <vector>

namespace Gemini2API
{
    namespace
    {
        bool FileExists(std::wstring const& path)
        {
            if (path.empty())
            {
                return false;
            }

            DWORD attributes = GetFileAttributesW(path.c_str());
            return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
        }

        std::wstring QuoteArg(std::wstring const& value)
        {
            if (value.empty())
            {
                return L"\"\"";
            }

            bool needsQuotes = value.find_first_of(L" \t\"") != std::wstring::npos;
            if (!needsQuotes)
            {
                return value;
            }

            std::wstring quoted = L"\"";
            for (wchar_t ch : value)
            {
                if (ch == L'"')
                {
                    quoted += L'\\';
                }
                quoted += ch;
            }
            quoted += L"\"";
            return quoted;
        }

        void CloseHandleIfSet(HANDLE& handle)
        {
            if (handle)
            {
                CloseHandle(handle);
                handle = nullptr;
            }
        }

        bool CreateInheritablePipe(HANDLE& readHandle, HANDLE& writeHandle)
        {
            SECURITY_ATTRIBUTES attributes{};
            attributes.nLength = sizeof(attributes);
            attributes.bInheritHandle = TRUE;

            if (!CreatePipe(&readHandle, &writeHandle, &attributes, 0))
            {
                return false;
            }

            if (!SetHandleInformation(readHandle, HANDLE_FLAG_INHERIT, 0))
            {
                CloseHandleIfSet(readHandle);
                CloseHandleIfSet(writeHandle);
                return false;
            }

            return true;
        }

        void CollectChildProcessIds(DWORD parentProcessId, std::vector<DWORD>& processIds)
        {
            HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (snapshot == INVALID_HANDLE_VALUE)
            {
                return;
            }

            PROCESSENTRY32W entry{};
            entry.dwSize = sizeof(entry);
            if (Process32FirstW(snapshot, &entry))
            {
                do
                {
                    if (entry.th32ParentProcessID == parentProcessId)
                    {
                        CollectChildProcessIds(entry.th32ProcessID, processIds);
                        processIds.push_back(entry.th32ProcessID);
                    }
                } while (Process32NextW(snapshot, &entry));
            }

            CloseHandle(snapshot);
        }

        void TerminateProcessId(DWORD processId, DWORD waitMilliseconds)
        {
            if (processId == 0 || processId == GetCurrentProcessId())
            {
                return;
            }

            HANDLE process = OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, processId);
            if (!process)
            {
                return;
            }

            DWORD exitCode = 0;
            if (GetExitCodeProcess(process, &exitCode) && exitCode == STILL_ACTIVE)
            {
                TerminateProcess(process, 0);
                WaitForSingleObject(process, waitMilliseconds);
            }
            CloseHandle(process);
        }

        void TerminateProcessTree(DWORD rootProcessId)
        {
            std::vector<DWORD> processIds;
            CollectChildProcessIds(rootProcessId, processIds);
            for (DWORD processId : processIds)
            {
                TerminateProcessId(processId, 2500);
            }
            TerminateProcessId(rootProcessId, 2500);
        }
    }

    BackendProcess::~BackendProcess()
    {
        Stop();
    }

    bool BackendProcess::Start(
        const std::wstring& pythonExe,
        const std::wstring& configPath,
        unsigned short port,
        const std::wstring& workingDirectory,
        const std::wstring& supervisorExe)
    {
        if (IsRunning())
        {
            return true;
        }

        HANDLE stdoutWrite = nullptr;
        HANDLE stderrWrite = nullptr;
        if (!CreateInheritablePipe(m_stdoutRead, stdoutWrite) || !CreateInheritablePipe(m_stderrRead, stderrWrite))
        {
            CloseHandles();
            if (stdoutWrite) CloseHandle(stdoutWrite);
            if (stderrWrite) CloseHandle(stderrWrite);
            return false;
        }

        std::wstringstream command;
        m_usingSupervisor = FileExists(supervisorExe);
        if (m_usingSupervisor)
        {
            command
                << QuoteArg(supervisorExe)
                << L" run "
                << QuoteArg(pythonExe)
                << L" "
                << QuoteArg(configPath)
                << L" "
                << port
                << L" 15";
        }
        else
        {
            command
                << QuoteArg(pythonExe)
                << L" -m gemini_web2api --config "
                << QuoteArg(configPath)
                << L" --port "
                << port;
        }

        bool started = StartCommand(command.str(), workingDirectory, stdoutWrite, stderrWrite);
        CloseHandleIfSet(stdoutWrite);
        CloseHandleIfSet(stderrWrite);
        if (!started)
        {
            CloseHandles();
            return false;
        }

        return true;
    }

    bool BackendProcess::StartCommand(
        std::wstring const& commandLine,
        std::wstring const& workingDirectory,
        HANDLE stdoutWrite,
        HANDLE stderrWrite)
    {
        STARTUPINFOW startupInfo{};
        startupInfo.cb = sizeof(startupInfo);
        startupInfo.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
        startupInfo.wShowWindow = SW_HIDE;
        startupInfo.hStdOutput = stdoutWrite;
        startupInfo.hStdError = stderrWrite;
        startupInfo.hStdInput = nullptr;

        PROCESS_INFORMATION processInfo{};
        std::vector<wchar_t> mutableCommand(commandLine.begin(), commandLine.end());
        mutableCommand.push_back(L'\0');

        m_jobHandle = CreateJobObjectW(nullptr, nullptr);
        if (!m_jobHandle)
        {
            return false;
        }

        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!SetInformationJobObject(
            m_jobHandle,
            JobObjectExtendedLimitInformation,
            &limits,
            sizeof(limits)))
        {
            CloseHandles();
            return false;
        }

        BOOL created = CreateProcessW(
            nullptr,
            mutableCommand.data(),
            nullptr,
            nullptr,
            TRUE,
            CREATE_NO_WINDOW | CREATE_SUSPENDED,
            nullptr,
            workingDirectory.empty() ? nullptr : workingDirectory.c_str(),
            &startupInfo,
            &processInfo);

        if (!created)
        {
            CloseHandles();
            return false;
        }

        if (!AssignProcessToJobObject(m_jobHandle, processInfo.hProcess))
        {
            TerminateProcess(processInfo.hProcess, 0);
            WaitForSingleObject(processInfo.hProcess, 5000);
            CloseHandle(processInfo.hThread);
            CloseHandle(processInfo.hProcess);
            CloseHandles();
            return false;
        }

        m_processHandle = processInfo.hProcess;
        m_threadHandle = processInfo.hThread;
        m_processId = processInfo.dwProcessId;

        if (ResumeThread(m_threadHandle) == static_cast<DWORD>(-1))
        {
            TerminateProcess(m_processHandle, 0);
            WaitForSingleObject(m_processHandle, 5000);
            CloseHandles();
            return false;
        }

        return true;
    }

    void BackendProcess::Stop()
    {
        if (m_processHandle)
        {
            DWORD exitCode = 0;
            if (GetExitCodeProcess(m_processHandle, &exitCode) && exitCode == STILL_ACTIVE)
            {
                TerminateProcessTree(m_processId);
                if (m_jobHandle)
                {
                    TerminateJobObject(m_jobHandle, 0);
                }
                TerminateProcess(m_processHandle, 0);
                WaitForSingleObject(m_processHandle, 5000);
            }
        }

        CloseHandles();
        m_processId = 0;
    }

    bool BackendProcess::IsRunning() const
    {
        if (!m_processHandle)
        {
            return false;
        }

        DWORD exitCode = 0;
        return GetExitCodeProcess(m_processHandle, &exitCode) && exitCode == STILL_ACTIVE;
    }

    unsigned long BackendProcess::ProcessId() const
    {
        return m_processId;
    }

    bool BackendProcess::IsUsingSupervisor() const
    {
        return m_usingSupervisor;
    }

    void BackendProcess::CloseHandles()
    {
        CloseHandleIfSet(m_threadHandle);
        CloseHandleIfSet(m_processHandle);
        CloseHandleIfSet(m_stdoutRead);
        CloseHandleIfSet(m_stderrRead);
        CloseHandleIfSet(m_jobHandle);
        m_processId = 0;
        m_usingSupervisor = false;
    }
}
