# Run a local demo: starts Directory + 3 relays and runs client (Windows PowerShell)
# Usage: Right-click -> Run with PowerShell, or from PowerShell: .\run_demo.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root

# Ensure PYTHONPATH points to repo root
$env:PYTHONPATH = $root

Write-Host "Starting Directory on port 9000..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python -m onion_routing.directory --host 127.0.0.1 --port 9000"
Start-Sleep -Milliseconds 400

Write-Host "Starting relays..."
Start-Process powershell -ArgumentList "-NoExit","-Command","python -m onion_routing.relay --relay-id relayA --host 127.0.0.1 --port 9101 --directory-host 127.0.0.1 --directory-port 9000 --capacity 5 --cell-size 16384"
Start-Process powershell -ArgumentList "-NoExit","-Command","python -m onion_routing.relay --relay-id relayB --host 127.0.0.1 --port 9102 --directory-host 127.0.0.1 --directory-port 9000 --capacity 3 --cell-size 16384"
Start-Process powershell -ArgumentList "-NoExit","-Command","python -m onion_routing.relay --relay-id relayC --host 127.0.0.1 --port 9103 --directory-host 127.0.0.1 --directory-port 9000 --capacity 2 --cell-size 16384"

Write-Host "Waiting 1s for relays to register..."
Start-Sleep -Seconds 1

Write-Host "Running client (single-shot)..."
python -m onion_routing.client --directory-host 127.0.0.1 --directory-port 9000 --hops 3 --destination demo://echo --message "demo run" --cell-size 16384

Pop-Location

Write-Host "Demo script completed. Close processes manually when done." 
