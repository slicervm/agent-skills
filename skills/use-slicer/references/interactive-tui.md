# Driving Interactive TUIs and Agents

`slicer vm exec` is one-shot and has no TTY, so it cannot run an interactive
program (a coding agent like OpenCode/Claude Code, a REPL, an installer)
directly. The fix is tmux: give the program a terminal owned by a tmux server,
then type into it with `send-keys` and read it back with `capture-pane`.

There are two placements for that tmux server. **Prefer the guest-side
pattern** — it is fully scriptable with `vm exec` alone, needs no TTY on
either end, and the session survives between calls.

## Pattern A — tmux inside the guest, driven by `vm exec` (preferred)

```bash
VM_NAME=$(slicer vm add sbox --tag workflow=tui-probe | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"

# 1. Start a tmux server + session inside the VM (tmux daemonises itself,
#    so plain exec is fine; bg exec works too)
slicer vm exec "$VM_NAME" --uid 1000 -- 'tmux new-session -d -s agent -x 220 -y 50'

# 2. Launch the TUI inside that session
slicer vm exec "$VM_NAME" --uid 1000 -- "tmux send-keys -t agent 'cd ~/work && opencode' Enter"

# 3. Wait for the TUI to draw, then send it work
slicer vm exec "$VM_NAME" --uid 1000 -- 'tmux capture-pane -t agent -p' | grep -q 'Ask anything' \
  || sleep 5
slicer vm exec "$VM_NAME" --uid 1000 -- "tmux send-keys -t agent 'Fix the failing test in pkg/api' Enter"

# 4. Loop capture-pane to observe progress — this is your assertion surface
slicer vm exec "$VM_NAME" --uid 1000 -- 'tmux capture-pane -t agent -p'
slicer vm exec "$VM_NAME" --uid 1000 -- 'tmux capture-pane -t agent -p -S -200'   # with scrollback
```

Every step is a stateless exec round-trip, so this scales to driving many VMs
in parallel, and the guest session keeps running between calls (and after you
disconnect entirely).

## Pattern B — host-side tmux + `vm shell` (watch it live)

When a human wants to see or touch the session, run the interactive bridge
inside a **host** tmux pane and puppeteer the pane:

```bash
tmux new-session -d -s probe -x 220 -y 50
tmux send-keys -t probe 'slicer vm shell VM_NAME' Enter
sleep 3   # login banner
tmux send-keys -t probe 'cd ~/work && opencode' Enter
tmux send-keys -t probe 'Fix the failing test in pkg/api' Enter
tmux capture-pane -t probe -p
```

Anyone on the host can now `tmux attach -t probe` to watch or take over.
The shell bridge detaches with `Ctrl+]`.

The patterns compose: start the session guest-side (Pattern A), and when you
want eyes on it, bridge in with `vm shell` + `tmux attach -t agent` from a
host pane (Pattern B).

## Notes

- `-x 220 -y 50` sets the virtual terminal size. Many TUIs render badly at
  the default 80x24; give them room.
- Poll `capture-pane` for the TUI's ready marker (its input prompt) before
  sending the task — sending too early types into the shell instead.
- **Relax the agent's permission gates before unattended runs** — permission
  prompts stall the session with nobody there to approve them. Inside a
  disposable Slicer VM the VM itself is the guardrail, so auto-approve is
  reasonable: `claude --dangerously-skip-permissions`, or for OpenCode set
  `"permission": {"bash": "allow", "edit": "allow"}` in `opencode.json`.
  Alternatively, watch for the prompt in `capture-pane` output ("Permission
  required") and answer it with `send-keys`.
- `send-keys` types literally and needs an explicit `Enter`. Control keys are
  named: `tmux send-keys -t agent C-c`, `Escape`, `Up`.
- **Do not create multi-line files through `send-keys` or an interactive
  heredoc.** Create the complete script/configuration locally and copy it with
  `slicer vm cp`, then validate it inside the VM. Sending only
  `cat > file <<'EOF'` leaves Bash at its `>` continuation prompt if the body
  or terminator is delayed, truncated, or lands in the wrong pane. If that has
  happened, send `C-c`, confirm the normal prompt has returned, and switch to
  local staging plus `vm cp`.
- Typical use: SDET-style testing of TUIs and coding agents — send a prompt,
  capture the screen, assert on what it shows, all from an orchestrating
  agent.
