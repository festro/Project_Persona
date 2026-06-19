<#
.SYNOPSIS
  Per-OS egress baseline (Windows / Windows Firewall) -- Project_Persona Phase 0.5.

.DESCRIPTION
  Default-deny OUTBOUND containment for the local-first stack. SCRIPTED, NOT enforced by
  manage.py -- run it deliberately. See docs/egress_baseline_design_20260619.md.

  Two modes (very different blast radius):
    - DEFAULT (process-scoped): outbound BLOCK rules (group "PersonaEgress") for the
      stack's own binaries (llama-server.exe). Contains the persona stack without touching
      the rest of the machine. Loopback is exempt from Windows Firewall by default, so the
      API <-> llama-server (127.0.0.1) path is unaffected.
    - -Strict (host-wide): set the active profile DefaultOutboundAction=Block + allow
      rules. True host-wide default-deny -- powerful but can lock out the whole box. Only
      for a dedicated appliance host.

  -Provision adds DNS(53)+HTTPS(443) allowances (under -Strict) so downloads work; remove
  it again afterwards.

  STATUS: written + reviewed on the Linux dev surface; LIVE WINDOWS VERIFY IS OWED.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\egress_baseline.ps1 -Plan
  powershell -ExecutionPolicy Bypass -File scripts\egress_baseline.ps1 -Apply        # process-scoped (run as admin)
  powershell -ExecutionPolicy Bypass -File scripts\egress_baseline.ps1 -Apply -Strict -Provision
  powershell -ExecutionPolicy Bypass -File scripts\egress_baseline.ps1 -Remove
#>
[CmdletBinding(DefaultParameterSetName = 'Status')]
param(
  [Parameter(ParameterSetName = 'Status')] [switch]$Status,
  [Parameter(ParameterSetName = 'Plan')]   [switch]$Plan,
  [Parameter(ParameterSetName = 'Apply')]  [switch]$Apply,
  [Parameter(ParameterSetName = 'Remove')] [switch]$Remove,
  [switch]$Strict,
  [switch]$Provision
)

$ErrorActionPreference = 'Stop'
$Group = 'PersonaEgress'
$Root  = Split-Path -Parent $PSScriptRoot
$LlamaExe = Join-Path $Root 'llama_cpp\windows\llama-server.exe'

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Require-Admin {
  if (-not (Test-Admin)) {
    Write-Error "This action changes firewall state and needs an elevated (Administrator) shell."
    exit 4
  }
}

function Show-Plan {
  $posture = if ($Provision) { 'PROVISION (DNS+HTTPS open)' } else { 'SERVE (locked)' }
  $mode    = if ($Strict)    { 'STRICT host-wide default-deny' } else { 'process-scoped block' }
  Write-Host "# egress baseline -- mode: $mode ; posture: $posture"
  Write-Host "# (dry print; nothing applied. Apply with: -Apply [-Strict] [-Provision] in an admin shell)"
  if ($Strict) {
    Write-Host "Set-NetFirewallProfile -Profile <active> -DefaultOutboundAction Block"
    Write-Host "Allow: loopback (implicit), established (implicit)"
    if ($Provision) { Write-Host "Allow: UDP/TCP 53 (DNS), TCP 443 (HTTPS)" }
    Write-Host "Group '$Group' allow-rules for the above; everything else outbound = blocked."
  } else {
    Write-Host "New-NetFirewallRule -Group $Group -Direction Outbound -Action Block -Program `"$LlamaExe`""
    Write-Host "(loopback exempt by default -> API<->llama on 127.0.0.1 unaffected)"
  }
}

function Get-Posture {
  $rules = Get-NetFirewallRule -Group $Group -ErrorAction SilentlyContinue
  if (-not $rules) { return 'none' }
  $profile = Get-NetFirewallProfile -ErrorAction SilentlyContinue |
             Where-Object { $_.Enabled -eq $true } | Select-Object -First 1
  if ($profile -and $profile.DefaultOutboundAction -eq 'Block') { return 'strict' }
  return 'process-scoped'
}

switch ($PSCmdlet.ParameterSetName) {
  'Status' {
    $p = Get-Posture
    switch ($p) {
      'none'           { Write-Host "egress baseline: NOT loaded (no '$Group' rules)" }
      'strict'         { Write-Host "egress baseline: LOADED -- STRICT host-wide default-deny" }
      'process-scoped' { Write-Host "egress baseline: LOADED -- process-scoped block ('$Group')" }
    }
  }
  'Plan' { Show-Plan }
  'Apply' {
    Require-Admin
    Show-Plan
    if ($Strict) {
      $active = Get-NetFirewallProfile | Where-Object { $_.Enabled -eq $true }
      foreach ($pr in $active) {
        New-NetFirewallRule -Group $Group -DisplayName "PersonaEgress allow loopback" `
          -Direction Outbound -Action Allow -RemoteAddress 127.0.0.1 -Profile $pr.Name | Out-Null
        if ($Provision) {
          New-NetFirewallRule -Group $Group -DisplayName "PersonaEgress allow DNS" `
            -Direction Outbound -Action Allow -Protocol UDP -RemotePort 53 -Profile $pr.Name | Out-Null
          New-NetFirewallRule -Group $Group -DisplayName "PersonaEgress allow HTTPS" `
            -Direction Outbound -Action Allow -Protocol TCP -RemotePort 443 -Profile $pr.Name | Out-Null
        }
        Set-NetFirewallProfile -Name $pr.Name -DefaultOutboundAction Block
      }
      Write-Host "OK: STRICT host-wide default-deny applied. Roll back: -Remove"
    } else {
      if (-not (Test-Path $LlamaExe)) {
        Write-Warning "llama-server.exe not found at $LlamaExe; creating the block rule anyway (it matches by path when present)."
      }
      New-NetFirewallRule -Group $Group -DisplayName "PersonaEgress block llama-server outbound" `
        -Direction Outbound -Action Block -Program $LlamaExe | Out-Null
      Write-Host "OK: process-scoped block applied for llama-server.exe. Roll back: -Remove"
    }
  }
  'Remove' {
    Require-Admin
    if ((Get-Posture) -eq 'strict') {
      foreach ($pr in (Get-NetFirewallProfile | Where-Object { $_.Enabled -eq $true })) {
        Set-NetFirewallProfile -Name $pr.Name -DefaultOutboundAction Allow
      }
      Write-Host "Restored DefaultOutboundAction=Allow on active profiles."
    }
    $rules = Get-NetFirewallRule -Group $Group -ErrorAction SilentlyContinue
    if ($rules) { $rules | Remove-NetFirewallRule; Write-Host "Removed '$Group' rules." }
    else { Write-Host "nothing to remove (no '$Group' rules)." }
  }
}
