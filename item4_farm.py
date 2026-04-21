import socket
import subprocess
import time
import json

def run_farm():
    print("Slave Farm Orchestrator listening on 0.0.0.0:9999...")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind aggressively to all interfaces
    server.bind(("0.0.0.0", 9999))
    server.listen(5)
    
    # Ensure binary compiled
    subprocess.run(["cargo", "build", "--release", "--quiet"], check=True)
    
    try:
        while True:
            conn, addr = server.accept()
            data = conn.recv(1024).decode()
            if not data:
                conn.close()
                continue
                
            req = json.loads(data)
            n = req['n']
            t = req['t']
            print(f"[{addr[0]}] -> Master commanded {t} concurrent slaves for N={n}")
            
            # Build dynamic config
            with open("config.txt", "w") as f:
                f.write(f"MASTER={addr[0]}\n")
                for i in range(t):
                    f.write(f"SLAVE=0.0.0.0:{8001+i}\n")
                    
            # Spawn slaves
            procs = []
            for i in range(t):
                port = 8001 + i
                cmd = ["cargo", "run", "--release", "--quiet", "--", str(n), str(port), "1", "config.txt"]
                procs.append(subprocess.Popen(cmd))
                
            time.sleep(1.5) # Allow the network stack to flush and bind all the ports natively
            conn.sendall(b"READY")
            conn.close()
            
            # Wait for master to push data and slaves to automatically exit upon ACK
            for p in procs:
                p.wait()
            
    except KeyboardInterrupt:
        print("\nSlave Farm shut down safely!")
        
if __name__ == "__main__":
    run_farm()
