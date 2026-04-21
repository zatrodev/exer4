.PHONY: baseline core_affine clean

baseline:
	@echo "Building release binary (Items 1 & 2 Baseline)..."
	@cargo build --release
	@echo ""
	@echo "--- Spinning up Slaves concurrently (NO Core Affinity) ---"
	@cargo run --release -- 4000 8001 1 config.txt & \
	cargo run --release -- 4000 8002 1 config.txt & \
	echo "Wait sequence initialized: 2 seconds for sockets to stabilize..." && \
	sleep 2 && \
	echo "" && \
	echo "--- Spinning up Master (NO Core Affinity) ---" && \
	cargo run --release -- 4000 9000 0 config.txt

core_affine:
	@echo "Building release binary (Optimized for Peak Performance)..."
	@cargo build --release
	@echo ""
	@echo "--- Spinning up Slaves concurrently with Core Affinity ---"
	@cargo run --release -- 4000 8001 1 config.txt 1 & \
	cargo run --release -- 4000 8002 1 config.txt 2 & \
	echo "Wait sequence initialized: 2 seconds for sockets to stabilize..." && \
	sleep 2 && \
	echo "" && \
	echo "--- Spinning up Master with Core Affinity ---" && \
	cargo run --release -- 4000 9000 0 config.txt 0

clean:
	@cargo clean

benchmark_baseline:
	@echo "LRP04 Table 1 Benchmark Sequence started..."
	python3 benchmark.py baseline

benchmark_core_affine:
	@echo "LRP04 Table 2 Core-Affine Sequence started..."
	python3 benchmark.py core_affine

deploy_slaves:
	@echo "Binding Remote Procedure Protocol for PC #2 Farm Orchestration..."
	python3 item4_farm.py

deploy_master:
	@echo "Executing synchronized cross-network bandwidth benchmarking to PC #2..."
	python3 item4_master.py
