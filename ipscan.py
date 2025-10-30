import random
import subprocess
import platform
import threading
import time
import socket
import http.client
import ssl
from urllib.parse import urlparse

OUTPUT_FILE = "live_ips.txt"
MAX_HITS = 10         # Number of responsive IPs to find
MAX_THREADS = 50      # Number of concurrent threads
WAIT_TIME = 0.01      # Time between thread launches

COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    3306: "MySQL"
}

live_ips = []
live_ips_lock = threading.Lock()
output_lock = threading.Lock()
found_event = threading.Event()

# Determine platform-specific ping command
system_platform = platform.system()
if system_platform == "Windows":
    PING_CMD = ["ping", "-n", "1", "-w", "1000"]
else:
    PING_CMD = ["ping", "-c", "1", "-W", "1"]



def get_website_info(ip):
    # Try reverse DNS
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        hostname = None

    redirect_location = None
    html_title = None

    try:
        conn = http.client.HTTPConnection(ip, timeout=2)
        conn.request("GET", "/", headers={"Host": ip})
        response = conn.getresponse()

        if "location" in response.getheaders_dict():
            redirect_location = response.getheader("location")

        body = response.read(2048).decode(errors='ignore')
        if "<title>" in body.lower():
            start = body.lower().find("<title>") + 7
            end = body.lower().find("</title>", start)
            html_title = body[start:end].strip()
        conn.close()
    except Exception:
        pass

    return {
        "reverse_dns": hostname,
        "redirect": redirect_location,
        "title": html_title
    }


def random_ip():
    while True:
        ip = ".".join(str(random.randint(1, 254)) for _ in range(4))
        if not ip.startswith(("0.", "10.", "127.", "192.168.", "172.")):
            return ip

def ping_ip(ip):
    try:
        result = subprocess.run(PING_CMD + [ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False

def worker():
    while not found_event.is_set():
        ip = random_ip()
        if ping_ip(ip):
            with live_ips_lock:
                if len(live_ips) >= MAX_HITS:
                    found_event.set()
                    return
                live_ips.append(ip)
                print(f"✅ {ip} is alive ({len(live_ips)}/{MAX_HITS})")
                with output_lock:
                    with open(OUTPUT_FILE, "a") as f:
                        f.write(ip + "\n")
                if len(live_ips) >= MAX_HITS:
                    found_event.set()
        else:
            print(f"❌ {ip} no response")

def scan_ports(ip):
    open_ports = []
    for port, name in COMMON_PORTS.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append((port, name))
        except Exception:
            pass
    return open_ports

def run_port_scans():
    print("\n🔎 Starting port scan on live IPs...")
    with open(OUTPUT_FILE, "a") as f:
        for ip in live_ips:
            ports = scan_ports(ip)
            if ports:
                print(f"[+] {ip} open ports: " + ", ".join(f"{p}/{n}" for p, n in ports))
                f.write(f"{ip} open ports: " + ", ".join(f"{p}/{n}" for p, n in ports) + "\n")
                if any(p == 80 for p, _ in ports):  # If HTTP is open
                    info = get_website_info(ip)
                    if info["reverse_dns"]:
                        f.write(f" ↳ reverse DNS: {info['reverse_dns']}\n")
                    if info["redirect"]:
                        f.write(f" ↳ HTTP redirect: {info['redirect']}\n")
                    if info["title"]:
                        f.write(f" ↳ Website title: {info['title']}\n")

            else:
                print(f"[-] {ip} has no open common ports.")
                f.write(f"{ip} has no open common ports.\n")

def main():
    print(f"Launching {MAX_THREADS} threads to find {MAX_HITS} live IPs...\n")
    threads = []

    for _ in range(MAX_THREADS):
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()
        threads.append(t)
        time.sleep(WAIT_TIME)

    for t in threads:
        t.join()

    print(f"\n🎉 Found {len(live_ips)} live IPs. Saved to {OUTPUT_FILE}")
    run_port_scans()

if __name__ == "__main__":
    main()
