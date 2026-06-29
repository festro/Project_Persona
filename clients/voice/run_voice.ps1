<#
  Convenience wrapper around persona_voice.py using the in-repo portable Python.
  Passes all arguments through. Examples:
    .\run_voice.ps1 selftest
    .\run_voice.ps1 say "Hello there"
    .\run_voice.ps1 ask "What is 2 plus 2?"
    .\run_voice.ps1 turn .\speech.wav
    .\run_voice.ps1 listen --seconds 5     (needs: python -m pip install sounddevice)

  Override the target API with $env:PERSONA_API (default http://192.168.8.114:8000).
#>
param([Parameter(ValueFromRemainingArguments = $true)] $Args)

$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$py = Join-Path $Root "portable\python\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py (Join-Path $PSScriptRoot "persona_voice.py") @Args
exit $LASTEXITCODE
