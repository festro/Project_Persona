[CmdletBinding()]
param(
    [string]$Distro = "",
    [string]$RepoWin = "D:\Projects\Git\Project_Persona",
    [string]$WslRepoRel = "Git/Project_Persona",
    [ValidateSet("all","preflight","sync","pullback","model","caps","setup","profiles","up","dispatch","smoke","mirror","logs","status","down")]
    [string]$Stage = "all",
    [switch]$Gpu,
    [switch]$SkipHermes,
    [switch]$SkipDeps,
    [switch]$Prune,
    [string]$PersonaModel = "",
    [string]$ModelUrl = "",
    [string]$JobId = "sim-001",
    [string]$Title = "Summarize the H2 design doc",
    [string]$Body  = "Read docs/h2_bridge_design_20260613_0204.md and write a 5-line summary.",
    [int]$DispatchTicks = 6,
    [int]$TickSleep = 10
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$DistroArgs = @()
if ($Distro -ne "") { $DistroArgs = @("-d", $Distro) }

$LogFile = Join-Path $RepoWin "logs\wsl_h2_sim.log"
try { $null = New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) -ErrorAction SilentlyContinue } catch { }

function Write-Log([string]$m) {
    Write-Host $m
    try { Add-Content -LiteralPath $LogFile -Value $m -Encoding UTF8 } catch { }
}

function ConvertTo-WslPath([string]$p) {
    $full = $p
    try { $full = (Resolve-Path -LiteralPath $p).Path } catch { }
    $drive = $full.Substring(0,1).ToLower()
    $rest = $full.Substring(2).Replace('\','/')
    return "/mnt/$drive$rest"
}

$Prelude = @'
set -euo pipefail
export NO_COLOR=1
export TERM=dumb
export AI_ROOT="$HOME/__WSLREL__"
export TASKS_DB="$AI_ROOT/data/tasks.db"
export HERMES_HOME="$AI_ROOT/persona/profiles/default"
export HERMES_KANBAN_HOME="$AI_ROOT/run/hermes_kanban"
export HERMES_CLI="$AI_ROOT/env_hermes/bin/hermes"
export HERMES_BRIDGE_TENANT="persona"
export PATH="$HOME/.local/bin:$PATH"
export SJ='__JOBID__'
export ST='__TITLE__'
export SB='__BODY__'
'@

function Expand-Body([string]$stageBody) {
    $cpu   = if ($Gpu) { "0" } else { "1" }
    $skiph = if ($SkipHermes) { "1" } else { "0" }
    $skipd = if ($SkipDeps) { "1" } else { "0" }
    $prune = if ($Prune) { "1" } else { "0" }
    $safeTitle = $Title.Replace("'", "")
    $safeBody  = $Body.Replace("'", "")
    $out = ($Prelude + "`n" + $stageBody)
    $out = $out.Replace('__WSLREL__', $WslRepoRel)
    $out = $out.Replace('__SRCMNT__', (ConvertTo-WslPath $RepoWin))
    $out = $out.Replace('__CPU__',    $cpu)
    $out = $out.Replace('__SKIPH__',  $skiph)
    $out = $out.Replace('__SKIPDEPS__', $skipd)
    $out = $out.Replace('__PRUNE__',  $prune)
    $out = $out.Replace('__JOBID__',  $JobId)
    $out = $out.Replace('__TITLE__',  $safeTitle)
    $out = $out.Replace('__BODY__',   $safeBody)
    $out = $out.Replace('__PMODEL__', $PersonaModel.Replace("'", ""))
    $out = $out.Replace('__MURL__',   $ModelUrl.Replace("'", ""))
    $out = $out.Replace('__TICKS__',  "$DispatchTicks")
    $out = $out.Replace('__SLEEP__',  "$TickSleep")
    return $out
}

function Invoke-Wsl([string]$stageBody, [switch]$AllowFail) {
    $cmd = Expand-Body $stageBody
    $b64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($cmd))
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $code = 0
    try {
        & wsl @DistroArgs -- bash -lc "echo $b64 | base64 -d > /tmp/h2_stage.sh && bash /tmp/h2_stage.sh" 2>&1 | ForEach-Object {
            $line = "$_" -replace '\x1b\[[0-9;]*[A-Za-z]', '' -replace '\x1b\][^\x07]*\x07', ''
            Write-Host $line
            try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch { }
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEAP
    }
    if (-not $AllowFail -and $code -ne 0) {
        throw "WSL stage exited with code $code"
    }
}

function Test-Wsl {
    $null = Get-Command wsl -ErrorAction Stop
    Write-Host "==> WSL detected. Distros:"
    & wsl --list --quiet
    if ($LASTEXITCODE -ne 0) { throw "wsl --list failed; is WSL installed?" }
}

$BodyPreflight = @'
echo "==> WSL preflight"
uname -a
echo "user: $(whoami)   home: $HOME"
echo "python3: $(python3 --version 2>&1)"
echo "git:     $(git --version 2>&1)"
echo "uv:      $(command -v uv >/dev/null 2>&1 && uv --version || echo 'absent (installer will add it)')"
echo "AI_ROOT target: $AI_ROOT"
'@

$BodySync = @'
echo "==> Sync working tree from Windows into WSL native fs"
SRC="__SRCMNT__"
[ -d "$SRC" ] || { echo "ERROR: source not found: $SRC"; exit 1; }
base="$(basename "$SRC")"
parent="$(dirname "$SRC")"
mkdir -p "$HOME/Git"
tar -C "$parent" \
  --exclude="$base/.git" \
  --exclude="$base/models" \
  --exclude="$base/llama_cpp" \
  --exclude="$base/env" \
  --exclude="$base/env_hermes" \
  --exclude="$base/portable" \
  --exclude="$base/run/hermes_kanban" \
  --exclude="$base/__pycache__" \
  -cf - "$base" | tar -C "$HOME/Git" -xf -
chmod +x "$AI_ROOT"/scripts/*.sh 2>/dev/null || true
chmod +x "$AI_ROOT"/*.sh 2>/dev/null || true
echo "synced to $AI_ROOT"
ls "$AI_ROOT" | head
'@

$BodyPullback = @'
echo "==> Reverse sync: WSL clone (primary) -> D:\ redundant copy (authored tree only)"
DST="__SRCMNT__"
[ -d "$DST" ] || { echo "ERROR: D:\ destination not found at $DST"; exit 1; }
if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync not installed in WSL. Install once: sudo apt-get install -y rsync"
  exit 1
fi
PRUNE='__PRUNE__'
DEL=""
if [ "$PRUNE" = "1" ]; then DEL="--delete"; echo "[pullback] PRUNE on: files absent in WSL will be removed from D:\ (excludes protected)"; fi
echo "[pullback] $AI_ROOT/  ->  $DST/"
rsync -rlt --modify-window=2 $DEL \
  --exclude='.git/' \
  --exclude='models/' \
  --exclude='env/' --exclude='env_hermes/' --exclude='env_webui/' --exclude='.venv/' --exclude='venv/' \
  --exclude='llama_cpp/' \
  --exclude='portable/' \
  --exclude='run/hermes_kanban/' --exclude='run/*.pid' --exclude='run/*.sock' \
  --exclude='logs/' --exclude='data/' --exclude='inbox/' --exclude='openwebui/' \
  --exclude='__pycache__/' --exclude='*.pyc' \
  --exclude='run/node_capabilities.json' --exclude='run/jobs/' --exclude='run/jobs.jsonl' \
  --exclude='*.bak' \
  "$AI_ROOT/" "$DST/"
echo "[pullback] done (prune=$PRUNE). NEXT, on Windows: cd $DST ; git status ; commit + push to origin."
echo "[pullback] NOTE: .git, models/, env*, llama_cpp/, portable/ and runtime are PROTECTED (Windows-only + heavy artifacts never touched)."
'@

$BodyModel = @'
echo "==> Ensure the persona GGUF is cached + reload. Config is the COMMITTED per-host"
echo "    file in D:\ (run/config.<host>.toml), synced down -- NOT patched in the clone."
cd "$AI_ROOT"
PMODEL='__PMODEL__'
MURL='__MURL__'
if [ -n "$PMODEL" ]; then
  mkdir -p models
  if [ ! -f "models/$PMODEL" ]; then
    if [ -n "$MURL" ]; then
      echo "[model] models/$PMODEL absent -- fetching ~4.7GB from $MURL (no progress meter; takes a while)"
      curl -fL --retry 3 -C - --no-progress-meter -o "models/$PMODEL.part" "$MURL"
      mv "models/$PMODEL.part" "models/$PMODEL"
      echo "[model] download complete"
    else
      echo "ERROR: models/$PMODEL absent and no -ModelUrl supplied to fetch it"
      exit 1
    fi
  fi
  echo "[model] gguf present: $(du -h "models/$PMODEL" | cut -f1)  models/$PMODEL"
else
  echo "[model] no -PersonaModel; relying on the per-host config + already-cached gguf"
fi
echo "[model] effective config (after [base]/[runtime]/[linux]/[host] merge):"
python3 manage.py status 2>/dev/null | grep -E 'model=|ctx=|host_config' || true
echo "[model] stopping any running stack so 'up' reloads with the current config (manage.py up skips a live server)"
python3 manage.py down >/dev/null 2>&1 || true
'@

$BodySetup = @'
echo "==> Native stack install (uv Hermes flow + services venv + llama build)"
cd "$AI_ROOT"
CPU_ONLY=__CPU__ SKIP_DEPS=__SKIPDEPS__ SKIP_HERMES=__SKIPH__ AI_ROOT="$AI_ROOT" bash scripts/setup_native_stack.sh
'@

$BodyProfiles = @'
echo "==> Persona profile + kanban init"
cd "$AI_ROOT"
bash scripts/init_profiles.sh >/dev/null 2>&1 && echo "[profiles normalized]" || echo "[init_profiles warning]"
if [ ! -f "$AI_ROOT/persona/config.yaml" ] && [ -f "$AI_ROOT/persona/profiles/default/config.yaml" ]; then
  cp "$AI_ROOT/persona/profiles/default/config.yaml" "$AI_ROOT/persona/config.yaml"
  echo "seeded persona/config.yaml from profiles/default (Hermes resolves the 'default' kanban assignee's HERMES_HOME to the ROOT, which reads <root>/config.yaml)"
fi
if [ -f "$AI_ROOT/persona/config.yaml" ]; then
  "$AI_ROOT/env_hermes/bin/python" - "$AI_ROOT/persona/config.yaml" <<'PY'
import sys, yaml
p = sys.argv[1]
d = yaml.safe_load(open(p)) or {}
d.setdefault('model', {})['context_length'] = 65536
for k, v in (d.get('auxiliary') or {}).items():
    if isinstance(v, dict):
        v['context_length'] = 65536
yaml.safe_dump(d, open(p, 'w'), sort_keys=False)
PY
  cp "$AI_ROOT/persona/config.yaml" "$AI_ROOT/persona/profiles/default/config.yaml"
  echo "ensured context_length=65536 on model + all auxiliary models (Hermes 64K gate; the small sim model is under that)"
fi
mkdir -p "$HERMES_KANBAN_HOME"
if [ -x "$HERMES_CLI" ]; then
  "$HERMES_CLI" -p default config check 2>&1 | grep -iE "version|required|missing|error|invalid" | head -8 || true
  "$HERMES_CLI" kanban init 2>&1 | tail -2 || true
else
  echo "WARN: $HERMES_CLI not found (run -Stage setup, or you used -SkipHermes)"
fi
'@

$BodyUp = @'
echo "==> Bring up persona stack (llama + API) in WSL"
cd "$AI_ROOT"
python3 manage.py up || echo "WARN: manage.py up returned nonzero (model present in models/?)"
sleep 3
python3 manage.py status || true
echo "--- /health ---"
curl -s 127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null | grep -Ei '"status"|task_store|delegate' \
  || echo "WARN: API /health not responding yet (check that a GGUF is in $AI_ROOT/models/ and config.toml [linux] PERSONA_MODEL matches)"
'@

$BodyDispatch = @'
echo "==> One dispatcher pass"
if [ -x "$HERMES_CLI" ]; then "$HERMES_CLI" kanban dispatch; else echo "no hermes CLI"; fi
'@

$BodySmoke = @'
echo "==> H2 smoke: delegate -> dispatch -> mirror"
cd "$AI_ROOT"
if ! curl -sf -m 5 127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "ERROR: persona API not responding on 127.0.0.1:8000 -- run -Stage up first (the background stack may have been torn down between WSL invocations)."
  exit 1
fi
PAYLOAD=$(python3 -c 'import json,os;print(json.dumps({"job_id":os.environ["SJ"],"title":os.environ["ST"],"body":os.environ["SB"],"assignee":"default"}))')
echo "--- delegate ---"
curl -s -X POST 127.0.0.1:8000/agent/delegate -H 'content-type: application/json' -d "$PAYLOAD"; echo
echo "--- bridge tick (create card) ---"
python3 tools/hermes_bridge.py --once || true
for i in $(seq 1 __TICKS__); do
  if [ -x "$HERMES_CLI" ]; then "$HERMES_CLI" kanban dispatch >/dev/null 2>&1 || true; fi
  python3 tools/hermes_bridge.py --once >/dev/null 2>&1 || true
  st=$(curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status'))" 2>/dev/null || echo "?")
  echo "tick $i [$(date +%H:%M:%S)]: status=$st"
  case "$st" in ok|error|timeout|blocked) break;; esac
  sleep __SLEEP__
done
echo "=== final persona /jobs row ==="
curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -m json.tool 2>/dev/null || echo "(no row)"
TID=$(curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -c "import sys,json;print(json.load(sys.stdin).get('hermes_task_id') or '')" 2>/dev/null || echo "")
if [ -n "$TID" ] && [ -x "$HERMES_CLI" ]; then
  echo "=== hermes card $TID ==="
  "$HERMES_CLI" kanban show "$TID" 2>/dev/null || true
  echo "=== worker log $TID (tail 30) ==="
  tail -30 "$HERMES_KANBAN_HOME/kanban/logs/$TID.log" 2>/dev/null || echo "(no worker log)"
fi
'@

$BodyMirror = @'
echo "==> mirror existing delegated job: $SJ (no new delegate)"
cd "$AI_ROOT"
for i in $(seq 1 __TICKS__); do
  if [ -x "$HERMES_CLI" ]; then "$HERMES_CLI" kanban dispatch >/dev/null 2>&1 || true; fi
  python3 tools/hermes_bridge.py --once >/dev/null 2>&1 || true
  st=$(curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status'))" 2>/dev/null || echo "?")
  echo "tick $i [$(date +%H:%M:%S)]: status=$st"
  case "$st" in ok|error|timeout|blocked) break;; esac
  sleep __SLEEP__
done
echo "=== final persona /jobs row ==="
curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -m json.tool 2>/dev/null || echo "(no row)"
TID=$(curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -c "import sys,json;print(json.load(sys.stdin).get('hermes_task_id') or '')" 2>/dev/null || echo "")
if [ -n "$TID" ] && [ -x "$HERMES_CLI" ]; then
  echo "=== worker log $TID (tail 40) ==="
  tail -40 "$HERMES_KANBAN_HOME/kanban/logs/$TID.log" 2>/dev/null || echo "(no worker log)"
fi
'@

$BodyCaps = @'
echo "==> GPU / accelerator capability probe (deciding GPU offload feasibility in WSL)"
cd "$AI_ROOT"
export LD_LIBRARY_PATH="$AI_ROOT/llama_cpp/build/bin:${LD_LIBRARY_PATH:-}"
echo "----- GPU hardware (lspci) -----"
lspci 2>/dev/null | grep -iE 'vga|3d controller|display' || echo "(lspci unavailable / no GPU line)"
echo "----- WSL GPU paravirt (/dev/dxg + driver libs) -----"
if [ -e /dev/dxg ]; then echo "/dev/dxg PRESENT (WSL2 GPU passthrough available)"; else echo "(no /dev/dxg -- GPU not exposed to WSL)"; fi
ls /usr/lib/wsl/lib 2>/dev/null | tr '\n' ' '; echo
echo "----- nvidia-smi (NVIDIA only) -----"
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 || echo "(no nvidia-smi)"
echo "----- Vulkan ICDs -----"
ls /usr/share/vulkan/icd.d/ 2>/dev/null || echo "(no icd.d -- Vulkan loader/driver not installed)"
echo "----- vulkaninfo --summary -----"
command -v vulkaninfo >/dev/null && vulkaninfo --summary 2>/dev/null | grep -iE 'deviceName|deviceType|driverName|driverInfo|apiVersion' | head -24 || echo "(vulkaninfo absent -- apt install vulkan-tools)"
echo "----- glslc (required to BUILD the Vulkan backend) -----"
command -v glslc >/dev/null && glslc --version 2>&1 | head -2 || echo "(glslc absent -- apt install glslang-tools or shaderc)"
echo "----- current llama-server build version/backends -----"
"$AI_ROOT/llama_cpp/build/bin/llama-server" --version 2>&1 | head -6 || echo "(no llama-server binary)"
echo "----- llama-server --list-devices (what it can offload to) -----"
"$AI_ROOT/llama_cpp/build/bin/llama-server" --list-devices 2>&1 | head -20 || true
echo "----- manage.py capabilities (accel summary) -----"
python3 manage.py capabilities 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('accel_selected =',d.get('accel_selected'));print('accel_present  =',[ (a.get('vendor'),a.get('device'),a.get('backends')) for a in d.get('accel_present',[])]);print('memory_model   =',d.get('memory_model'));print('vram_mb        =',d.get('vram_mb'));print('llama_compiled =',d.get('llama_backends_compiled'))" 2>/dev/null || echo "(capabilities parse failed)"
'@

$BodyLogs = @'
echo "==> WSL stack + worker logs (surfaced into the D:\ orchestrator transcript logs/wsl_h2_sim.log)"
cd "$AI_ROOT"
echo "----- llama-server logs/persona.log (tail 60) -----"
tail -n 60 logs/persona.log 2>/dev/null || echo "(no persona.log)"
echo "----- API logs/api.log (tail 20) -----"
tail -n 20 logs/api.log 2>/dev/null || echo "(no api.log)"
echo "----- live llama-server process -----"
ps -o pid,pcpu,pmem,etime,comm -C llama-server 2>/dev/null || ps aux | grep '[l]lama-server' || echo "(llama-server not running)"
echo "----- job $SJ -----"
curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -m json.tool 2>/dev/null || echo "(no job $SJ)"
TID=$(curl -s "127.0.0.1:8000/jobs/$SJ" | python3 -c "import sys,json;print(json.load(sys.stdin).get('hermes_task_id') or '')" 2>/dev/null || echo "")
if [ -n "$TID" ]; then
  echo "----- worker log $TID (tail 80) -----"
  tail -n 80 "$HERMES_KANBAN_HOME/kanban/logs/$TID.log" 2>/dev/null || echo "(no $TID.log)"
  echo "----- workspace listing $TID -----"
  ls -la "$HERMES_KANBAN_HOME/kanban/workspaces/$TID" 2>/dev/null || echo "(no workspace dir)"
fi
echo "----- newest 5 worker logs -----"
ls -t "$HERMES_KANBAN_HOME"/kanban/logs/*.log 2>/dev/null | head -5 || echo "(none)"
'@

$BodyStatus = @'
echo "==> Status"
cd "$AI_ROOT"
python3 manage.py status || true
if [ -x "$HERMES_CLI" ]; then "$HERMES_CLI" kanban diagnostics || true; fi
'@

$BodyDown = @'
echo "==> Tear down persona stack"
cd "$AI_ROOT"
python3 manage.py down || true
if [ -x "$HERMES_CLI" ]; then "$HERMES_CLI" gateway stop 2>/dev/null || true; fi
'@

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Log ("`n" + ("=" * 72))
Write-Log "Project_Persona -- WSL H2 simulation   $ts"
Write-Log ("RepoWin : {0}" -f $RepoWin)
Write-Log ("WSL repo: ~/{0}   GPU={1}   SkipHermes={2}   SkipDeps={3}   Stage={4}" -f $WslRepoRel, $Gpu.IsPresent, $SkipHermes.IsPresent, $SkipDeps.IsPresent, $Stage)
if ($PersonaModel -ne "") {
    Write-Log ("Model   : {0}  (gguf cache only; model/ctx/parallel come from run/config.<host>.toml)" -f $PersonaModel)
}
Write-Log ("LogFile : {0}" -f $LogFile)
Write-Log ("=" * 72)

Test-Wsl

$run = {
    param($name)
    Write-Log ("`n### {0}  @ {1} ###" -f $name.ToUpper(), (Get-Date -Format "HH:mm:ss"))
    switch ($name) {
        "preflight" { Invoke-Wsl $BodyPreflight }
        "sync"      { Invoke-Wsl $BodySync }
        "pullback"  { Invoke-Wsl $BodyPullback }
        "model"     { Invoke-Wsl $BodyModel }
        "setup"     { Invoke-Wsl $BodySetup }
        "profiles"  { Invoke-Wsl $BodyProfiles }
        "up"        { Invoke-Wsl $BodyUp -AllowFail }
        "dispatch"  { Invoke-Wsl $BodyDispatch -AllowFail }
        "smoke"     { Invoke-Wsl $BodySmoke -AllowFail }
        "mirror"    { Invoke-Wsl $BodyMirror -AllowFail }
        "caps"      { Invoke-Wsl $BodyCaps -AllowFail }
        "logs"      { Invoke-Wsl $BodyLogs -AllowFail }
        "status"    { Invoke-Wsl $BodyStatus -AllowFail }
        "down"      { Invoke-Wsl $BodyDown -AllowFail }
    }
}

if ($Stage -eq "all") {
    foreach ($s in @("preflight","sync","model","setup","profiles","up","smoke","status")) { & $run $s }
    Write-Log "`n==> ALL stages done. Stack left UP. Tear down with: -Stage down"
} else {
    & $run $Stage
}

Write-Log "`nDone."
