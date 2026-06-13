"""Fix deployment: upload missing file, check port, rebuild."""
import paramiko
import os
import time

HOST = "152.42.180.195"
PORT = 22
USER = "root"
PASSWD = "13863533025Li"
PROJECT_DIR = r"D:\workspaces\2api\gemini2api"
REMOTE_DIR = "/opt/gemini2api"

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, check=True, timeout=120):
    print(f"  >>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  {out[:3000]}")
    if err:
        print(f"  [stderr] {err[:3000]}")
    if check and exit_code != 0:
        print(f"  [WARN] exit code: {exit_code}")
    return exit_code, out, err

def main():
    print("=" * 50)
    print("Fix deployment")
    print("=" * 50)

    ssh = get_ssh()
    print("  Connected!")

    # Step 1: Upload missing config.example.json
    print("\n[1] Uploading missing config.example.json...")
    sftp = ssh.open_sftp()
    local_path = os.path.join(PROJECT_DIR, "config.example.json")
    remote_path = REMOTE_DIR + "/config.example.json"
    sftp.put(local_path, remote_path)
    print(f"  Uploaded to {remote_path}")
    sftp.close()

    # Step 2: Check what's using port 8081
    print("\n[2] Checking port 8081 usage...")
    run_cmd(ssh, "docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'")
    run_cmd(ssh, "ss -tlnp | grep 8081 || echo 'Port 8081 not in use by non-docker'")

    # Step 3: Stop and rebuild
    print("\n[3] Stopping old container and rebuilding...")
    run_cmd(ssh, "cd /opt/gemini2api && docker compose -f docker-compose.local.yml down", check=False)
    run_cmd(ssh, "docker stop gemini-web2api 2>/dev/null; docker rm gemini-web2api 2>/dev/null", check=False)

    # Rebuild
    print("\n[4] Building Docker image...")
    code, out, err = run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.local.yml up -d --build", check=False, timeout=300)

    # Wait for startup
    print("\n  Waiting 8 seconds for container to start...")
    time.sleep(8)

    # Step 5: Verify
    print("\n[5] Verifying deployment...")
    run_cmd(ssh, "docker ps --filter name=gemini --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'")
    run_cmd(ssh, "docker logs gemini-web2api --tail 30 2>&1 || echo 'Container logs not available'")
    run_cmd(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/v1/models || echo 'API not responding'")
    run_cmd(ssh, "curl -s http://localhost:8081/v1/models 2>&1 | head -200")

    ssh.close()
    print("\n" + "=" * 50)
    print("Fix deployment complete!")
    print(f"API: http://{HOST}:8081/v1")
    print(f"Dashboard: http://{HOST}:8081/dashboard")
    print("=" * 50)

if __name__ == "__main__":
    main()
