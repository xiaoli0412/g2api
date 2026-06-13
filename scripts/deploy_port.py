"""Check available ports in 8090-8099 range and deploy gemini2api."""
import paramiko
import time

HOST = "152.42.180.195"
PORT = 22
USER = "root"
PASSWD = "13863533025Li"
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
        print(f"  {out[:5000]}")
    if err:
        print(f"  [stderr] {err[:3000]}")
    if check and exit_code != 0:
        print(f"  [WARN] exit code: {exit_code}")
    return exit_code, out, err

def main():
    print("=" * 50)
    print("Deploy gemini2api on 809x port")
    print("=" * 50)

    ssh = get_ssh()
    print("  Connected!")

    # Step 1: Find available port
    print("\n[1] Checking port availability (8090-8099)...")
    _, out, _ = run_cmd(ssh, "ss -tlnp | grep -E ':809[0-9]' || echo 'All 809x ports available'")
    
    # Find first available port
    used_ports = set()
    for line in out.split("\n"):
        for p in range(8090, 8100):
            if f":{p}" in line:
                used_ports.add(p)
    
    chosen_port = None
    for p in range(8090, 8100):
        if p not in used_ports:
            chosen_port = p
            break
    
    if not chosen_port:
        print("  ERROR: No available port in 8090-8099!")
        ssh.close()
        return
    
    print(f"\n  Chosen port: {chosen_port}")

    # Step 2: Update docker-compose to use the chosen port
    print(f"\n[2] Updating docker-compose to use port {chosen_port}...")
    
    # Create a docker-compose with the chosen port
    compose_content = f"""services:
  gemini-web2api:
    build: .
    container_name: gemini-web2api
    ports:
      - "{chosen_port}:8081"
    volumes:
      - ./config.json:/app/config.json
      - ./cookie.txt:/app/cookie.txt
    restart: unless-stopped
"""
    # Write the compose file on the server
    escaped = compose_content.replace("'", "'\\''")
    run_cmd(ssh, f"cat > {REMOTE_DIR}/docker-compose.yml << 'COMPOSEEOF'\n{escaped}\nCOMPOSEEOF")

    # Step 3: Remove old container if any
    print("\n[3] Removing old container...")
    run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.local.yml down 2>/dev/null", check=False)
    run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose down 2>/dev/null", check=False)
    run_cmd(ssh, "docker stop gemini-web2api 2>/dev/null; docker rm gemini-web2api 2>/dev/null", check=False)

    # Step 4: Build and start
    print(f"\n[4] Building and starting on port {chosen_port}...")
    code, out, err = run_cmd(ssh, f"cd {REMOTE_DIR} && docker compose up -d --build", check=False, timeout=300)

    # Wait
    print("\n  Waiting 10 seconds for container to start...")
    time.sleep(10)

    # Step 5: Verify
    print("\n[5] Verifying deployment...")
    run_cmd(ssh, "docker ps --filter name=gemini --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'")
    run_cmd(ssh, f"docker logs gemini-web2api --tail 30 2>&1 || echo 'No logs'")
    
    print(f"\n  Testing API on port {chosen_port}...")
    run_cmd(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{chosen_port}/v1/models 2>&1 || echo 'Not responding'")
    run_cmd(ssh, f"curl -s http://localhost:{chosen_port}/v1/models 2>&1 | head -500")

    ssh.close()
    print("\n" + "=" * 50)
    print(f"Deployment complete on port {chosen_port}!")
    print(f"API: http://{HOST}:{chosen_port}/v1")
    print(f"Dashboard: http://{HOST}:{chosen_port}/dashboard")
    print("=" * 50)

if __name__ == "__main__":
    main()
