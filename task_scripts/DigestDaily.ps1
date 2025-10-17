# DigestDaily.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "C:\Users\Sharks\Desktop\CryptoNews"
$env:ENV = "prod"

if (!(Test-Path ".state\logs")) { New-Item -ItemType Directory ".state\logs" | Out-Null }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log   = ".state\logs\digest_$stamp.log"

# Use Start-Process so both streams are captured deterministically
$p = Start-Process -FilePath "python" -ArgumentList "-B","run_digest.py" `
     -RedirectStandardOutput $log -RedirectStandardError $log -NoNewWindow -PassThru
$p.WaitForExit()
"ExitCode: $($p.ExitCode)" | Add-Content $log
