use std::error::Error;
use std::fmt::Write as _;
use std::io::{self, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread;
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

type Result<T> = std::result::Result<T, Box<dyn Error>>;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug)]
struct ProbeResult {
    reachable: bool,
    url: String,
    status: Option<u16>,
    error: Option<String>,
}

#[derive(Debug)]
struct BackendHealth {
    ready: bool,
    root: ProbeResult,
    models: ProbeResult,
    admin: ProbeResult,
    stats: ProbeResult,
}

#[derive(Debug)]
struct StartReport {
    mode: String,
    started: bool,
    process_id: Option<u32>,
    base_url: String,
    health: BackendHealth,
    message: String,
}

#[derive(Debug)]
struct ExitReport {
    process_id: u32,
    code: Option<i32>,
    success: bool,
}

enum ChildOutputMode {
    Piped,
    Null,
}

struct ManagedChild {
    child: Child,
    #[cfg(windows)]
    job: process_tree::JobObject,
}

impl ManagedChild {
    fn spawn(mut command: Command) -> Result<Self> {
        #[cfg(windows)]
        {
            command.creation_flags(CREATE_NO_WINDOW);
            let job = process_tree::JobObject::create()?;
            let mut child = command.spawn()?;
            if let Err(err) = job.assign_child(&child) {
                let _ = child.kill();
                let _ = child.wait();
                return Err(err.into());
            }
            Ok(Self { child, job })
        }

        #[cfg(not(windows))]
        {
            Ok(Self {
                child: command.spawn()?,
            })
        }
    }

    fn id(&self) -> u32 {
        self.child.id()
    }

    fn terminate(&mut self) {
        #[cfg(windows)]
        {
            let _ = self.job.terminate(0);
        }
        let _ = self.child.kill();
    }

    fn wait(&mut self) -> io::Result<ExitStatus> {
        self.child.wait()
    }
}

#[cfg(windows)]
mod process_tree {
    use std::ffi::c_void;
    use std::io;
    use std::mem::{size_of, zeroed};
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;
    use std::ptr::{null, null_mut};

    type Bool = i32;
    type Dword = u32;
    type Handle = *mut c_void;
    type SizeT = usize;
    type Uint = u32;
    type UlongPtr = usize;

    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS: i32 = 9;
    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Dword = 0x0000_2000;

    #[repr(C)]
    #[allow(non_snake_case)]
    struct IoCounters {
        ReadOperationCount: u64,
        WriteOperationCount: u64,
        OtherOperationCount: u64,
        ReadTransferCount: u64,
        WriteTransferCount: u64,
        OtherTransferCount: u64,
    }

    #[repr(C)]
    #[allow(non_snake_case)]
    struct JobObjectBasicLimitInformation {
        PerProcessUserTimeLimit: i64,
        PerJobUserTimeLimit: i64,
        LimitFlags: Dword,
        MinimumWorkingSetSize: SizeT,
        MaximumWorkingSetSize: SizeT,
        ActiveProcessLimit: Dword,
        Affinity: UlongPtr,
        PriorityClass: Dword,
        SchedulingClass: Dword,
    }

    #[repr(C)]
    #[allow(non_snake_case)]
    struct JobObjectExtendedLimitInformation {
        BasicLimitInformation: JobObjectBasicLimitInformation,
        IoInfo: IoCounters,
        ProcessMemoryLimit: SizeT,
        JobMemoryLimit: SizeT,
        PeakProcessMemoryUsed: SizeT,
        PeakJobMemoryUsed: SizeT,
    }

    #[link(name = "kernel32")]
    extern "system" {
        fn CreateJobObjectW(attributes: *mut c_void, name: *const u16) -> Handle;
        fn SetInformationJobObject(
            job: Handle,
            info_class: i32,
            info: *mut c_void,
            info_length: Dword,
        ) -> Bool;
        fn AssignProcessToJobObject(job: Handle, process: Handle) -> Bool;
        fn TerminateJobObject(job: Handle, exit_code: Uint) -> Bool;
        fn CloseHandle(handle: Handle) -> Bool;
    }

    pub struct JobObject {
        handle: Handle,
    }

    impl JobObject {
        pub fn create() -> io::Result<Self> {
            unsafe {
                let handle = CreateJobObjectW(null_mut(), null());
                if handle.is_null() {
                    return Err(io::Error::last_os_error());
                }

                let mut limits: JobObjectExtendedLimitInformation = zeroed();
                limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                let ok = SetInformationJobObject(
                    handle,
                    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                    (&mut limits as *mut JobObjectExtendedLimitInformation).cast(),
                    size_of::<JobObjectExtendedLimitInformation>() as Dword,
                );
                if ok == 0 {
                    let err = io::Error::last_os_error();
                    let _ = CloseHandle(handle);
                    return Err(err);
                }

                Ok(Self { handle })
            }
        }

        pub fn assign_child(&self, child: &Child) -> io::Result<()> {
            unsafe {
                let process = child.as_raw_handle() as Handle;
                if AssignProcessToJobObject(self.handle, process) == 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            }
        }

        pub fn terminate(&self, exit_code: Uint) -> io::Result<()> {
            unsafe {
                if TerminateJobObject(self.handle, exit_code) == 0 {
                    return Err(io::Error::last_os_error());
                }
                Ok(())
            }
        }
    }

    impl Drop for JobObject {
        fn drop(&mut self) {
            unsafe {
                if !self.handle.is_null() {
                    let _ = CloseHandle(self.handle);
                    self.handle = null_mut();
                }
            }
        }
    }
}

fn endpoint(port: u16, path: &str) -> String {
    let normalized = if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    };
    format!("http://127.0.0.1:{port}{normalized}")
}

fn normalize_path(path: &str) -> String {
    if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    }
}

fn json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn json_optional_string(value: &Option<String>) -> String {
    value.as_ref().map_or_else(|| "null".to_string(), |item| json_string(item))
}

fn json_optional_u16(value: Option<u16>) -> String {
    value.map_or_else(|| "null".to_string(), |item| item.to_string())
}

fn json_optional_i32(value: Option<i32>) -> String {
    value.map_or_else(|| "null".to_string(), |item| item.to_string())
}

impl ProbeResult {
    fn to_json(&self) -> String {
        format!(
            "{{\"reachable\":{},\"url\":{},\"status\":{},\"error\":{}}}",
            self.reachable,
            json_string(&self.url),
            json_optional_u16(self.status),
            json_optional_string(&self.error)
        )
    }
}

impl BackendHealth {
    fn to_json(&self) -> String {
        format!(
            "{{\"ready\":{},\"root\":{},\"models\":{},\"admin\":{},\"stats\":{}}}",
            self.ready,
            self.root.to_json(),
            self.models.to_json(),
            self.admin.to_json(),
            self.stats.to_json()
        )
    }
}

impl StartReport {
    fn to_json(&self) -> String {
        let process_id = self
            .process_id
            .map_or_else(|| "null".to_string(), |item| item.to_string());
        format!(
            "{{\"mode\":{},\"started\":{},\"process_id\":{},\"base_url\":{},\"health\":{},\"message\":{}}}",
            json_string(&self.mode),
            self.started,
            process_id,
            json_string(&self.base_url),
            self.health.to_json(),
            json_string(&self.message)
        )
    }
}

impl ExitReport {
    fn to_json(&self) -> String {
        format!(
            "{{\"process_id\":{},\"code\":{},\"success\":{}}}",
            self.process_id,
            json_optional_i32(self.code),
            self.success
        )
    }
}

fn probe_path(port: u16, path: &str) -> ProbeResult {
    let url = endpoint(port, path);
    let request_path = normalize_path(path);
    let timeout = Duration::from_secs(2);
    let address = SocketAddr::from(([127, 0, 0, 1], port));

    let mut stream = match TcpStream::connect_timeout(&address, timeout) {
        Ok(stream) => stream,
        Err(err) => {
            return ProbeResult {
                reachable: false,
                url,
                status: None,
                error: Some(err.to_string()),
            };
        }
    };

    let _ = stream.set_read_timeout(Some(timeout));
    let _ = stream.set_write_timeout(Some(timeout));

    let request = format!(
        "GET {request_path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    );

    if let Err(err) = stream.write_all(request.as_bytes()) {
        return ProbeResult {
            reachable: false,
            url,
            status: None,
            error: Some(err.to_string()),
        };
    }

    let mut response = String::new();
    if let Err(err) = stream.read_to_string(&mut response) {
        return ProbeResult {
            reachable: false,
            url,
            status: None,
            error: Some(err.to_string()),
        };
    }

    let status = response
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok());
    let reachable = status.is_some_and(|code| (200..300).contains(&code));

    ProbeResult {
        reachable,
        url,
        status,
        error: if reachable {
            None
        } else {
            Some("backend returned a non-success HTTP response".to_string())
        },
    }
}

fn health(port: u16) -> BackendHealth {
    let root = probe_path(port, "/");
    let models = probe_path(port, "/v1/models");
    let admin = probe_path(port, "/admin");
    let stats = probe_path(port, "/admin/stats");
    let ready = root.reachable && models.reachable && admin.reachable && stats.reachable;

    BackendHealth {
        ready,
        root,
        models,
        admin,
        stats,
    }
}

fn start_backend(
    python: &str,
    config: &str,
    port: u16,
    output_mode: ChildOutputMode,
) -> Result<ManagedChild> {
    let port_arg = port.to_string();
    let mut command = Command::new(python);
    command
        .arg("-m")
        .arg("gemini_web2api")
        .arg("--config")
        .arg(config)
        .arg("--port")
        .arg(port_arg)
        .stdin(Stdio::null());

    match output_mode {
        ChildOutputMode::Piped => {
            command.stdout(Stdio::piped()).stderr(Stdio::piped());
        }
        ChildOutputMode::Null => {
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    ManagedChild::spawn(command).map_err(|err| {
        io::Error::new(
            io::ErrorKind::Other,
            format!("failed to start backend with {python}: {err}"),
        )
        .into()
    })
}

fn wait_ready(port: u16, timeout: Duration) -> BackendHealth {
    let start = Instant::now();
    loop {
        let result = health(port);
        if result.ready || start.elapsed() >= timeout {
            return result;
        }
        thread::sleep(Duration::from_millis(250));
    }
}

fn required_arg<'a>(args: &'a [String], index: usize, name: &str) -> Result<&'a str> {
    args.get(index).map(String::as_str).ok_or_else(|| {
        io::Error::new(io::ErrorKind::InvalidInput, format!("missing {name}")).into()
    })
}

fn parse_port(args: &[String], index: usize) -> Result<u16> {
    Ok(required_arg(args, index, "port")?.parse()?)
}

fn parse_timeout(args: &[String], index: usize) -> Result<u64> {
    Ok(args
        .get(index)
        .map(String::as_str)
        .unwrap_or("15")
        .parse()?)
}

fn print_usage() {
    println!("usage:");
    println!("  gemini2api-supervisor probe <port> [path]");
    println!("  gemini2api-supervisor status <port>");
    println!("  gemini2api-supervisor start <python> <config> <port> [timeout-seconds]");
    println!("  gemini2api-supervisor run <python> <config> <port> [timeout-seconds]");
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        print_usage();
        return Ok(());
    }

    match args[1].as_str() {
        "probe" => {
            let port = parse_port(&args, 2)?;
            let path = args.get(3).map(String::as_str).unwrap_or("/");
            println!("{}", probe_path(port, path).to_json());
        }
        "status" => {
            let port = parse_port(&args, 2)?;
            println!("{}", health(port).to_json());
        }
        "start" => {
            let python = required_arg(&args, 2, "python executable")?;
            let config = required_arg(&args, 3, "config path")?;
            let port = parse_port(&args, 4)?;
            let timeout_seconds = parse_timeout(&args, 5)?;
            let mut child = start_backend(python, config, port, ChildOutputMode::Piped)?;
            let ready = wait_ready(port, Duration::from_secs(timeout_seconds));
            let report = StartReport {
                mode: "smoke".to_string(),
                started: true,
                process_id: Some(child.id()),
                base_url: endpoint(port, "/").trim_end_matches('/').to_string(),
                health: ready,
                message: "smoke mode exits after readiness probing and terminates the child process".to_string(),
            };
            println!("{}", report.to_json());
            child.terminate();
            let _ = child.wait();
        }
        "run" => {
            let python = required_arg(&args, 2, "python executable")?;
            let config = required_arg(&args, 3, "config path")?;
            let port = parse_port(&args, 4)?;
            let timeout_seconds = parse_timeout(&args, 5)?;
            let mut child = start_backend(python, config, port, ChildOutputMode::Null)?;
            let process_id = child.id();
            let ready = wait_ready(port, Duration::from_secs(timeout_seconds));
            let is_ready = ready.ready;
            let report = StartReport {
                mode: "run".to_string(),
                started: true,
                process_id: Some(process_id),
                base_url: endpoint(port, "/").trim_end_matches('/').to_string(),
                health: ready,
                message: "run mode keeps the backend process alive until it exits or the supervisor is terminated".to_string(),
            };
            println!("{}", report.to_json());
            io::stdout().flush().ok();

            if !is_ready {
                child.terminate();
                let _ = child.wait();
                return Err(io::Error::new(
                    io::ErrorKind::TimedOut,
                    "backend did not become ready before timeout",
                )
                .into());
            }

            let status: ExitStatus = child.wait()?;
            let exit = ExitReport {
                process_id,
                code: status.code(),
                success: status.success(),
            };
            println!("{}", exit.to_json());
        }
        other => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("unknown command: {other}"),
            )
            .into());
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{endpoint, json_string};

    #[test]
    fn endpoint_normalizes_paths() {
        assert_eq!(endpoint(18081, "/"), "http://127.0.0.1:18081/");
        assert_eq!(endpoint(18081, "admin/stats"), "http://127.0.0.1:18081/admin/stats");
    }

    #[test]
    fn json_string_escapes_control_characters() {
        assert_eq!(json_string("a\"b\\c\n"), "\"a\\\"b\\\\c\\n\"");
    }
}
