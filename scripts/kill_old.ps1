$pids = @(25696, 24044, 20764, 14832, 19104, 10032, 22216)
foreach ($p in $pids) {
    try {
        Stop-Process -Id $p -Force -ErrorAction Stop
        Write-Host "Killed PID $p"
    } catch {
        Write-Host "PID $p already gone"
    }
}
Write-Host "All done"
