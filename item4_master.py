import socket
import subprocess
import time
import json
import csv
import re

REMOTE_IP = "10.12.63.254"

def generate_config(t):
    with open("config.txt", 'w') as f:
        f.write("MASTER=127.0.0.1\n") # Just a layout placeholder for Master's internal parsing logic
        for i in range(t):
            f.write(f"SLAVE={REMOTE_IP}:{8001 + i}\n")

def run_iteration(n, t):
    generate_config(t)
    
    # Notify farm over our RPC
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((REMOTE_IP, 9999))
        s.sendall(json.dumps({"n": n, "t": t}).encode())
        resp = s.recv(1024)
        s.close()
    except Exception as e:
        print(f"\n[!] TCP Hardware Failure: Could not establish sync socket to PC #2 ({REMOTE_IP}:9999). Is `make deploy_slaves` running there?")
        exit(1)
    
    if resp != b"READY":
        print("Farm protocol desync!")
        return 0.0
        
    master_cmd = ["cargo", "run", "--release", "--quiet", "--", str(n), "9000", "0", "config.txt"]
    result = subprocess.run(master_cmd, capture_output=True, text=True)
    out = result.stdout
    
    match = re.search(r"Master Time Elapsed[^\d]+([\d\.]+)\s*seconds", out)
    if match:
        return float(match.group(1))
    else:
        print(f"Error parsing runtime! Master output:\n{out}")
        return 0.0

def main():
    n_params = [4000, 8000, 16000]
    t_params = [2, 4, 8, 16]
    output_file = "Lab04_Item4_Network_Table.csv"
    
    print(f"Connecting to PC #2 Slave Farm Interface at {REMOTE_IP}...")
    subprocess.run(["cargo", "build", "--release", "--quiet"], check=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["n", "t", "Run 1", "Run 2", "Run 3", "Average Runtime (seconds)"])
        
        for n in n_params:
            for t in t_params:
                print(f"Dispatching payload array [N={n:<5} | t={t:<2}] over LAN ... ", end="", flush=True)
                times = []
                for _ in range(3):
                    times.append(run_iteration(n, t))
                
                avg = sum(times) / 3.0
                print(f"Time Avg: {avg:.4f}s")
                writer.writerow([n, t, f"{times[0]:.4f}", f"{times[1]:.4f}", f"{times[2]:.4f}", f"{avg:.4f}"])
                f.flush()
                
    print(f"\nPhase 4 Cross-PC Benchmarks finalized! Table extracted to: {output_file}")

if __name__ == "__main__":
    main()
