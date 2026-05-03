import subprocess
import time
import sys

def main():
    print("Starting network...")
    dir_proc = subprocess.Popen([sys.executable, "-m", "onion_routing.directory", "--port", "9090"])
    time.sleep(1)
    
    relays = []
    for i in range(1, 4):
        is_exit = ["--is-exit"] if i == 3 else []
        p = subprocess.Popen([
            sys.executable, "-m", "onion_routing.relay",
            "--relay-id", f"relay{i}",
            "--port", str(9100 + i),
            "--directory-port", "9090",
            "--capacity", "5"
        ] + is_exit)
        relays.append(p)
    
    time.sleep(2)
    
    print("Running benchmarks...")
    times = []
    for _ in range(5):
        start = time.time()
        subprocess.run([
            sys.executable, "-m", "onion_routing.client",
            "--directory-port", "9090",
            "--hops", "3",
            "--message", "benchmarking"
        ], stdout=subprocess.DEVNULL)
        times.append(time.time() - start)
        
    print(f"Metrics (3 hops, 16KB padding):")
    print(f"Individual runs (sec): {', '.join(f'{t:.3f}' for t in times)}")
    print(f"Average latency: {sum(times)/len(times):.3f} sec")
    
    for p in relays + [dir_proc]:
        p.terminate()

if __name__ == '__main__':
    main()
