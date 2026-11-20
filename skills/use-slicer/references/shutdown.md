# Shut down a VM and confirm it has stopped

For a persistent VM, use its name or hostname as `VM_REF`. On Firecracker,
use the active daemon's `config.shutdown_timeout` in whole seconds, rounded
up (60 when the key is absent). For a local Unix socket, check the config of
the daemon serving that socket. When its config is unavailable, choose a wait
for the task and state that assumption. On macOS, allow time for the guest's
stop jobs. Set `STOP_WAIT_SECONDS` to the chosen value. The example adds 10s
for acknowledgement and 20s for forced termination and status updates.

```bash
set -e -o pipefail
: "${STOP_WAIT_SECONDS:?Set the wait in seconds for this VM}"
deadline=$((SECONDS + STOP_WAIT_SECONDS + 10 + 20))
slicer vm shutdown "$VM_REF"
while true; do
  VM_JSON=$(slicer vm describe "$VM_REF" --json) || exit 1
  VM_STATE=$(printf '%s\n' "$VM_JSON" | jq -er '.status') || exit 1
  [ "$VM_STATE" = Stopped ] && break
  if (( SECONDS >= deadline )); then
    echo "$VM_REF is still $VM_STATE after shutdown." >&2
    exit 1
  fi
  sleep 2
done
```
