import subprocess
import time
import csv
import sys
import re

# ========================================================
# UPLB SWARM CONFIGURATION
# ========================================================
USERNAME = "rdsantos21"
PASSWORD = "5a4d7dc19f6abd296c705970dd88f8af"
OVERQUEEN_IP = "overqueen"

# The Overqueen is explicitly reserved. Do not list it here.
# Drone Mobile Legends Nodes:
DRONE_NODES = [
    "10.0.9.175", # zilong
    "10.0.9.164", # phoveus
    "10.0.9.139", # jawhead
    "10.0.9.143", # layla
    "10.0.9.179", # beatrix
    "10.0.9.136", # hilda
    "10.0.9.142", # khufra
    "10.0.9.129", # freya
    "10.0.9.137", # hylos
    "10.0.9.155", # lunox
    "10.0.9.167", # selena
    "10.0.9.176", # alucard
    "10.0.9.173", # yve
    "10.0.9.156", # mathilda
    "10.0.9.174", # zhuxin
    "10.0.9.135", # helcurt
]

# We must dedicate one separate Drone explicitly to act as the Master, 
# because executing heavy array creation on the Overqueen violates the rules!
MASTER_DRONE_IP = "10.0.9.185" # gusion (Node 17)

def generate_swarm_config(t):
    with open("config.txt", 'w') as f:
        f.write(f"MASTER={MASTER_DRONE_IP}:9000\n")
        # Distribute Slaves strictly across different physical cluster nodes
        for i in range(t):
            drone_ip = DRONE_NODES[i % len(DRONE_NODES)]
            # We can universally use Port 8001 since each Drone is its own entire physical computer
            f.write(f"SLAVE={drone_ip}:8001\n") 

    # Synchronize the configuration explicitly inside the Swarm network filesystem directly from your local laptop
    subprocess.run(["sshpass", "-p", PASSWORD, "scp", "-o", "StrictHostKeyChecking=no", "config.txt", f"{USERNAME}@{OVERQUEEN_IP}:/home/{USERNAME}/config.txt"], check=True)

def run_swarm_iteration(n, t):
    generate_swarm_config(t)
    
    slave_procs = []
    print(f"Deploying {t} Slaves across ICS Drones via SSH...")
    
    for i in range(t):
        drone_ip = DRONE_NODES[i % len(DRONE_NODES)]
        # We spawn the Rust process silently via SSH into the Drone's home directory NFS mount
        ssh_cmd = [
            "sshpass", "-p", PASSWORD,
            "ssh", "-o", "StrictHostKeyChecking=no", f"{USERNAME}@{drone_ip}", 
            f"cd /home/{USERNAME} && ./exer4_swarm {n} 8001 1 config.txt"
        ]
        slave_procs.append(subprocess.Popen(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
    # Extended sleep allows UPLB nodes to fully boot heavily laden NFS environment scripts
    time.sleep(5) 
    
    print(f"Executing Master payload sequentially on Drone {MASTER_DRONE_IP}...")
    
    # Trigger Master sequence remotely natively to bypass Overqueen execution restrictions
    master_cmd = [
        "sshpass", "-p", PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no", f"{USERNAME}@{MASTER_DRONE_IP}",
        f"cd /home/{USERNAME} && ./exer4_swarm {n} 9000 0 config.txt"
    ]
    
    # stdout=subprocess.PIPE explicitly buffers combining stderr so it can't evaluate to None
    try:
        result = subprocess.run(master_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = result.stdout if result.stdout else "[Empty System Response]"
    except FileNotFoundError:
        out = "[!] CRITICAL: 'sshpass' is not natively installed on this node! To fix it instantly, run: 'sudo apt install sshpass'"
        
    # Native output routing
    print("\n" + out.strip() + "\n")
    
    match = re.search(r"Master Time Elapsed[^\d]+([\d\.]+)\s*seconds", out)
    if match:
        elapsed = float(match.group(1))
        # Await Drone node shutdown signaling organically
        for p in slave_procs:
            p.wait()
        return elapsed
    else:
        print("[!] Master failed to synchronize. Purging hanging drone SSH connections...")
        for p in slave_procs:
            p.kill()  # Hard-wipe hanging sockets to prevent memory leaks!
        return 0.0

def main():
    n_params = [4000, 8000, 16000]
    t_params = [2, 4, 8, 16]
    output_file = "Lab04_Swarm_Table.csv"
    
    print("====================================")
    print("UPLB ICS COMPUTE SWARM COORDINATOR")
    print("====================================")
    
    # Secure laptop artifact compiling
    print("Building bare-metal binary on local Laptop...")
    subprocess.run(["cargo", "build", "--release", "--quiet"], check=True)
    
    print(f"Transferring payload seamlessly over SCP Gateway ({OVERQUEEN_IP})...")
    subprocess.run(["sshpass", "-p", PASSWORD, "scp", "-o", "StrictHostKeyChecking=no", "target/release/exer4", f"{USERNAME}@{OVERQUEEN_IP}:/home/{USERNAME}/exer4_swarm"], check=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["n", "t", "Run 1", "Run 2", "Run 3", "Average Runtime (seconds)"])
        
        for n in n_params:
            for t in t_params:
                print(f"\n[ORCHESTRATING CLUSTER FOR N={n} | Drones={t}]")
                times = []
                for rep in range(3):
                    # Smart Retry Mechanism
                    success_time = 0.0
                    for attempt in range(1, 6): # Try up to 5 times
                        val = run_swarm_iteration(n, t)
                        if val > 0.0:
                            success_time = val
                            break
                        print(f"--- Retrying benchmark phase (Attempt {attempt}/5) in 5 seconds... ---")
                        time.sleep(5)
                        
                    times.append(success_time)
                
                avg = sum(times) / 3.0
                print(f"Iteration Avg: {avg:.4f}s")
                writer.writerow([n, t, f"{times[0]:.4f}", f"{times[1]:.4f}", f"{times[2]:.4f}", f"{avg:.4f}"])
                f.flush()
                
    print(f"\nUPLB Swarm Execution Complete! Secure file extraction ready at: {output_file}")

if __name__ == "__main__":
    main()
