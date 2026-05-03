import argparse
import subprocess
import time
import sys
import os

def start_process(command, log_file=None):
    """Starts a non-blocking process with an optional log file."""
    try:
        if log_file:
            with open(log_file, "w") as f:
                return subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
        else:
            return subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
    except Exception as e:
        print(f"Failed to start process: {' '.join(command)}. Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Anonymity Network Driver")
    parser.add_argument("--dir-host", default="127.0.0.1", help="Directory node host")
    parser.add_argument("--dir-port", type=int, default=9090, help="Directory node port")
    parser.add_argument("--num-relays", type=int, default=3, help="Number of relays to start")
    parser.add_argument("--hops", type=int, default=3, help="Number of hops for the client")
    parser.add_argument("--message", default="hello from team demo", help="Message for client to send")
    parser.add_argument("--dest-host", default=None, help="Specific outbound host for the client payload (TCP route)")
    parser.add_argument("--dest-port", type=int, default=None, help="Specific outbound port for the client payload (TCP route)")
    args = parser.parse_args()

    processes = []
    
    # Ensure logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")

    print("[Driver] Starting Directory Node...")
    dir_cmd = [sys.executable, "-u", "-m", "onion_routing.directory", "--host", args.dir_host, "--port", str(args.dir_port)]
    dir_proc = start_process(dir_cmd, log_file="logs/directory.log")
    processes.append(dir_proc)

    # Wait for directory to be ready
    time.sleep(1)

    base_relay_port = 9100
    for i in range(1, args.num_relays + 1):
        relay_id = f"relay{i}"
        relay_port = base_relay_port + i
        capacity = max(1, 5 - i) # Variable capacities for testing
        is_exit = "--is-exit" if i == args.num_relays else "" 
        print(f"[Driver] Starting {relay_id} on port {relay_port} with capacity {capacity} {'(EXIT)' if is_exit else ''}...")
        
        relay_cmd = [
            sys.executable, "-u", "-m", "onion_routing.relay",
            "--relay-id", relay_id,
            "--host", "127.0.0.1",
            "--port", str(relay_port),
            "--directory-host", args.dir_host,
            "--directory-port", str(args.dir_port),
            "--capacity", str(capacity)
        ]
        if is_exit:
            relay_cmd.append(is_exit)
        
        p = start_process(relay_cmd, log_file=f"logs/{relay_id}.log")
        processes.append(p)

    # Allow relays to register
    time.sleep(2)

    print("\n[Driver] Starting Client...")
    client_cmd = [
        sys.executable, "-u", "-m", "onion_routing.client",
        "--directory-host", args.dir_host,
        "--directory-port", str(args.dir_port),
        "--hops", str(args.hops),
        "--message", args.message
    ]
    if args.dest_host and args.dest_port:
        client_cmd.extend(["--dest-host", args.dest_host, "--dest-port", str(args.dest_port)])
    
    # Run the client blocking, outputting to console
    subprocess.run(client_cmd)

    print("\n[Driver] Tearing down network...")
    for p in processes:
        p.terminate()
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()
            
    print("[Driver] Network tear down complete. Check the logs/ folder for detailed outputs.")

if __name__ == "__main__":
    main()
