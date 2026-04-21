import subprocess
import time
import csv
import sys
import re

def generate_config(num_slaves, filename="config.txt"):
    """Dynamically routes configuring multiple slaves."""
    with open(filename, 'w') as f:
        f.write("MASTER=127.0.0.1\n")
        f.write("# Dynamic Run parameters\n")
        for i in range(num_slaves):
            f.write(f"SLAVE=127.0.0.1:{8001 + i}\n")

def run_iteration(n, t, run_num, use_affinity):
    generate_config(t)
    
    slave_procs = []
    # Deploy Slaves
    for i in range(t):
        port = 8001 + i
        cmd = ["cargo", "run", "--release", "--quiet", "--", str(n), str(port), "1", "config.txt"]
        if use_affinity:
            cmd.append(str(i + 1))  # Offset slave processor mapping
            
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        slave_procs.append(p)
        
    time.sleep(1.5)  # Let TCP stack bind heavily dynamically
    
    # Deploy Master
    master_cmd = ["cargo", "run", "--release", "--quiet", "--", str(n), "9000", "0", "config.txt"]
    if use_affinity:
        master_cmd.append("0")

    result = subprocess.run(master_cmd, capture_output=True, text=True)
    out = result.stdout
    
    elapsed = 0.0
    match = re.search(r"Master Time Elapsed[^\d]+([\d\.]+)\s*seconds", out)
    if match:
        elapsed = float(match.group(1))
    else:
        print(f"Error parsing runtime! Dump:\n {out}")

    # Wait for the OS to kill sockets smoothly
    for p in slave_procs:
        p.wait()
        
    return elapsed

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    use_affinity = (mode == "core_affine")
    output_file = "Lab04_Item3_Table.csv" if use_affinity else "Lab04_Items1_2_Table.csv"
    
    n_params = [4000, 8000, 16000]
    t_params = [2, 4, 8, 16]
    
    print(f"Initializing CMSC 180 LRP04 Benchmark Engine")
    print(f"Mode: {'Item 3 (Core Affine)' if use_affinity else 'Items 1 & 2 (Baseline)'}")
    print("Compiling Release Binary...")
    subprocess.run(["cargo", "build", "--release", "--quiet"], check=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Time Elapsed (seconds)", "", "", "", "", ""])
        writer.writerow(["n", "t", "Run 1", "Run 2", "Run 3", "Average Runtime (seconds)"])
        
        for n in n_params:
            for t in t_params:
                print(f"Benchmarking [N={n:<5} | t={t:<2}] ... ", end="", flush=True)
                times = []
                for run_id in range(1, 4):
                    runtime = run_iteration(n, t, run_id, use_affinity)
                    times.append(runtime)
                
                avg = sum(times) / 3.0
                print(f"Done. Avg: {avg:.4f}s")
                writer.writerow([n, t, f"{times[0]:.4f}", f"{times[1]:.4f}", f"{times[2]:.4f}", f"{avg:.4f}"])
                f.flush()
                
    print(f"\nOptimization Complete! CSV generated at: {output_file}")

if __name__ == "__main__":
    main()
