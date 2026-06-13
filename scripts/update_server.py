"""Update server with bug-fixed code and redeploy."""
import paramiko
import os
import time

HOST = "152.42.180.195"
PORT = 22
USER = "root"
PASSWD = "13863533025Li"
PROJECT_DIR = r"D:\workspaces\2api\gemini2api"
REMOTE_DIR = "/opt/gemini2api"

# Only upload modified/fixed files
UPDATED_FILES = [
    "gemini_web2api/server.py",
    "gemini_web2api/adapters.py",
    "gemini_web2api/multimodal.py",
    "gemini_web2api/proxy_builtin.py",
    "auto_start.py",
]

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, timeout=180):
    print(f"  >>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  {out[:2000]}")
    if err and "Image" not in err[:100]:
        print(f"  [stderr] {err[:1000]}")
    return exit_code, out, err

def main():
    print("=" * 50)
    print("Update server with bug fixes")
    print("=" * 50)

    ssh = get_ssh()
    print("  Connected!")

    # Upload fixed files
    print("\n[1] Uploading fixed files...")
    sftp = ssh.open_sftp()
    for rel_path in UPDATED_FILES:
        local = os.path.join(PROJECT_DIR, rel_path.replace("/", os.sep))
        remote = REMOTE_DIR + "/" + rel_path
        if os.path.exists(local):
            sftp.put(local, remote)
            print(f"  Updated: {rel_path}")
        else:
            print(f"  SKIP: {rel_path} not found")
    sftp.close()

    # Rebuild Docker container
    print("\n[2] Rebuilding Docker container...")
    run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose up -d --build", timeout=300)

    # Wait for startup
    print("\n  Waiting 10 seconds...")
    time.sleep(10)

    # Verify
    print("\n[3] Verifying...")
    run_cmd(ssh, "docker ps --filter name=gemini --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'")
    run_cmd(ssh, "docker logs gemini-web2api --tail 15 2>&1")
    run_cmd(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8090/v1/models")
    run_cmd(ssh, "curl -s -H 'Authorization: Bearer sk-100412' http://localhost:8090/v1/models | head -200")

    ssh.close()
    print("\n" + "=" * 50)
    print("Server update complete!")
    print(f"API: http://{HOST}:8090/v1")
    print("=" * 50)

if __name__ == "__main__":
    main()
