"""Deploy gemini2api to remote server via paramiko."""
import paramiko
import os
import stat
import time
import sys

HOST = "152.42.180.195"
PORT = 22
USER = "root"
PASSWD = "13863533025Li"
PROJECT_DIR = r"D:\workspaces\2api\gemini2api"
REMOTE_DIR = "/opt/gemini2api"

# Files/dirs to upload
UPLOAD_ITEMS = [
    "gemini_web2api",       # directory
    "config.json",          # config
    "cookie.txt",           # cookie
    "requirements.txt",     # deps
    "Dockerfile",           # docker
    "docker-compose.local.yml",  # compose
]

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWD, timeout=30)
    return ssh

def run_cmd(ssh, cmd, check=True):
    print(f"  >>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(f"  {out}")
    if err:
        print(f"  [stderr] {err}")
    if check and exit_code != 0:
        print(f"  [WARN] exit code: {exit_code}")
    return exit_code, out, err

def upload_dir(sftp, local_dir, remote_dir):
    """Recursively upload a directory."""
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)
    
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = remote_dir + "/" + item
        
        # Skip __pycache__ and .pyc files
        if item == "__pycache__" or item.endswith(".pyc"):
            continue
            
        if os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path)
        else:
            size = os.path.getsize(local_path)
            print(f"  {remote_path} ({size} bytes)")
            sftp.put(local_path, remote_path)

def upload_file(sftp, local_path, remote_path):
    """Upload a single file."""
    size = os.path.getsize(local_path)
    print(f"  {remote_path} ({size} bytes)")
    sftp.put(local_path, remote_path)

def main():
    print("=" * 50)
    print("Deploy gemini2api to server")
    print(f"Server: {HOST}:{PORT}")
    print("=" * 50)
    
    # Step 1: Connect
    print("\n[1/5] Connecting to server...")
    ssh = get_ssh()
    print("  Connected!")
    
    # Step 2: Check Docker
    print("\n[2/5] Checking Docker environment...")
    code, out, _ = run_cmd(ssh, "docker --version")
    if code != 0:
        print("  Docker not found, installing...")
        run_cmd(ssh, "curl -fsSL https://get.docker.com | sh", check=False)
        run_cmd(ssh, "systemctl enable docker && systemctl start docker")
        code, out, _ = run_cmd(ssh, "docker --version")
        if code != 0:
            print("  ERROR: Failed to install Docker!")
            ssh.close()
            sys.exit(1)
    
    code2, out2, _ = run_cmd(ssh, "docker compose version 2>/dev/null || docker-compose --version 2>/dev/null")
    has_compose = code2 == 0
    print(f"  Docker Compose available: {has_compose}")
    
    # Step 3: Prepare remote directory
    print("\n[3/5] Preparing remote directory...")
    run_cmd(ssh, f"mkdir -p {REMOTE_DIR}")
    
    # Step 4: Upload files
    print("\n[4/5] Uploading project files...")
    sftp = ssh.open_sftp()
    
    for item in UPLOAD_ITEMS:
        local_path = os.path.join(PROJECT_DIR, item)
        remote_path = REMOTE_DIR + "/" + item
        
        if not os.path.exists(local_path):
            print(f"  [SKIP] {item} not found locally")
            continue
        
        if os.path.isdir(local_path):
            print(f"  Uploading directory: {item}/")
            upload_dir(sftp, local_path, remote_path)
        else:
            print(f"  Uploading file: {item}")
            upload_file(sftp, local_path, remote_path)
    
    sftp.close()
    print("  Upload complete!")
    
    # Step 5: Build and start Docker
    print("\n[5/5] Building and starting Docker container...")
    
    # Stop existing container if any
    run_cmd(ssh, "docker stop gemini-web2api 2>/dev/null; docker rm gemini-web2api 2>/dev/null", check=False)
    
    if has_compose:
        # Use docker compose
        run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.local.yml up -d --build", check=False)
    else:
        # Manual docker build and run
        run_cmd(ssh, f"cd {REMOTE_DIR} && docker build -t gemini-web2api .", check=False)
        run_cmd(ssh, f"docker run -d --name gemini-web2api -p 8081:8081 -v {REMOTE_DIR}/config.json:/app/config.json --restart unless-stopped gemini-web2api", check=False)
    
    # Wait for container to start
    print("\n  Waiting for container to start...")
    time.sleep(5)
    
    # Verify
    print("\n[VERIFY] Checking container status...")
    run_cmd(ssh, "docker ps --filter name=gemini-web2api --format '{{.Status}}'")
    run_cmd(ssh, "curl -s http://localhost:8081/ || echo 'Service not responding yet'")
    run_cmd(ssh, "docker logs gemini-web2api --tail 20 2>&1")
    
    ssh.close()
    print("\n" + "=" * 50)
    print("Deployment complete!")
    print(f"API: http://{HOST}:8081/v1")
    print(f"Dashboard: http://{HOST}:8081/dashboard")
    print("=" * 50)

if __name__ == "__main__":
    main()
