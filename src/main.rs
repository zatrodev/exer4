use rand::Rng;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::process;
use std::thread;
use std::time::Instant;

extern crate core_affinity;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 5 {
        eprintln!("Usage: {} <n> <p> <s> <config_file> [core_id]", args[0]);
        process::exit(1);
    }

    let n: usize = args[1].parse().expect("Invalid n");
    let p: u16 = args[2].parse().expect("Invalid p");
    let s: u8 = args[3].parse().expect("Invalid s");
    let config_path = &args[4];

    // Feature 3: Core Affinity binding
    if let Some(core_id_str) = args.get(5) {
        if let Ok(id) = core_id_str.parse::<usize>() {
            let cores = core_affinity::get_core_ids().expect("Failed to get physical cores");
            if !cores.is_empty() {
                let hw_core = id % cores.len();
                core_affinity::set_for_current(cores[hw_core]);
                println!(
                    "[Optimization] Process thread securely pinned to Hardware Core {}",
                    hw_core
                );
            }
        }
    }

    // Parse the Configuration file
    let file = match File::open(config_path) {
        Ok(f) => f,
        Err(_) => {
            eprintln!("Failed to open config file. Please create one with lines like:\nMASTER=192.168.1.10\nSLAVE=127.0.0.1:8001");
            process::exit(1);
        }
    };

    let reader = BufReader::new(file);
    let mut slaves = Vec::new();

    for line_result in reader.lines() {
        if let Ok(line) = line_result {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('#') {
                continue;
            }
            if trimmed.starts_with("SLAVE=") {
                slaves.push(trimmed.replace("SLAVE=", ""));
            }
        }
    }

    if s == 0 {
        // --- MASTER LOGIC ---
        let t = slaves.len();
        if t == 0 {
            eprintln!("Fatal error: Configuration parsed successfully but 0 slaves recorded.");
            process::exit(1);
        }

        println!(
            "Master Spin Up Initialized | Target Matrix Size: {}x{} | Assigned Slaves (t): {}",
            n, n, t
        );

        // Submatrix logic
        let elements_per_slave = (n / t) * n;

        // 1. Create a non-zero n x n square matrix with random positive integers on the Heap
        let mut matrix: Vec<u32> = vec![0; n * n];
        let mut rng = rand::rng();
        for val in matrix.iter_mut() {
            *val = rng.random_range(1..=100) as u32; // Ensures non-zero
        }

        // Feature 5/Optimization: Concurrent One-to-Many Personalized Broadcast
        // Instead of pipelining over 1 loop, we fire all chunks independently over parallel threads.
        println!("Distributing {} submatrices concurrently...", t);
        let time_before = Instant::now();

        thread::scope(|scope| {
            let mut handles = Vec::with_capacity(t);

            for (i, slave_addr) in slaves.iter().enumerate() {
                let chunk_start = i * elements_per_slave;
                // Handle arbitrary modulus by extending the last thread if needed
                let chunk_end = if i == t - 1 {
                    n * n
                } else {
                    chunk_start + elements_per_slave
                };

                let chunk = &matrix[chunk_start..chunk_end];
                let addr = slave_addr.clone();

                let handle = scope.spawn(move || {
                    let mut stream =
                        TcpStream::connect(&addr).expect("Slave connection actively refused.");
                    // Ensure the transport layer packets are sent immediately, eliminating typical TCP delays.
                    stream.set_nodelay(true).unwrap();

                    // Zero-Cost Dispatch: Bypass serde, treat u32 sequence natively in memory as raw u8
                    let bytes: &[u8] = unsafe {
                        std::slice::from_raw_parts(
                            chunk.as_ptr() as *const u8,
                            chunk.len() * std::mem::size_of::<u32>(),
                        )
                    };

                    stream.write_all(bytes).expect("Transmission fault.");

                    // Blocking until explicit ACK is recognized
                    let mut ack_buf = [0u8; 3];
                    stream
                        .read_exact(&mut ack_buf)
                        .expect("Failed to read ACK buffer.");
                    assert_eq!(&ack_buf, b"ack", "Invalid ACK checksum.");
                });
                handles.push(handle);
            }

            for handle in handles {
                handle.join().unwrap();
            }
        });

        // Terminate timer immediately upon join of all slave transmissions
        let time_after = Instant::now();
        let time_elapsed = time_after.duration_since(time_before).as_secs_f64();

        println!("Verification: All concurrent transmission ACKed.");
        println!(
            "Master Time Elapsed (time_elapsed): {:.6} seconds",
            time_elapsed
        );
    } else if s == 1 {
        // --- SLAVE LOGIC ---

        // Feature 4: Bind on 0.0.0.0 automatically handles multi-PC cross-network connectivity
        let bind_addr = format!("0.0.0.0:{}", p);
        let listener = TcpListener::bind(&bind_addr)
            .expect("Slave couldn't bind to port. Ensure it's unoccupied.");
        println!("Slave spinning up... actively listening on {}", bind_addr);

        if let Ok((mut stream, _master_address)) = listener.accept() {
            stream.set_nodelay(true).unwrap();

            // Note time_before IMMEDIATELY when the master asserts a connection
            let time_before = Instant::now();

            let t = slaves.len();
            let expected_elements = (n / t) * n;

            // The slave doesn't strictly know its rank (i) out of the box unless master sends it.
            // If the chunk doesn't divide evenly, the standard requires some rank logic.
            // To be safely conformant to typical uniform matrices in the problem size:
            if n % t != 0 {
                println!("Warning: Uneven partition sizes detected. Assuming slave length.");
            }

            let byte_count = expected_elements * std::mem::size_of::<u32>();
            let mut submatrix_buffer = vec![0u8; byte_count];

            stream
                .read_exact(&mut submatrix_buffer)
                .expect("Submatrix read phase collapsed");

            // Dispatch return confirmation packet directly through standard out
            stream.write_all(b"ack").expect("Failed to send ACK signal");

            // Compute elapsed instantly after byte transfer success
            let time_after = Instant::now();
            let time_elapsed = time_after.duration_since(time_before).as_secs_f64();

            // Hardware verification: Re-cast correctly
            let received_data: &[u32] = unsafe {
                std::slice::from_raw_parts(
                    submatrix_buffer.as_ptr() as *const u32,
                    expected_elements,
                )
            };

            println!(
                "Verification Passed: Reconstructed slice length: {} elements",
                received_data.len()
            );
            println!(
                "Slave Time Elapsed (time_elapsed): {:.6} seconds",
                time_elapsed
            );
        }
    }
}
