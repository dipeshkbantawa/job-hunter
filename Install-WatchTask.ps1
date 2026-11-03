# Creates the JobHunterWatch scheduled task: runs `hunter watch` at 09:00 and 18:00, and as soon as possible
# after a missed time. Notifications need you to be logged in. Run from PowerShell opened as administrator.
# To remove the task: Unregister-ScheduledTask -TaskName JobHunterWatch
$ErrorActionPreference = 'Stop'
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $PSScriptRoot `
    -Argument '/c .venv\Scripts\python.exe -m hunter watch >> data\watch-task.log 2>&1'
$triggers = @((New-ScheduledTaskTrigger -Daily -At '09:00'), (New-ScheduledTaskTrigger -Daily -At '18:00'))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'JobHunterWatch' -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal -Description 'job-hunter: notify about new notices on vacancy pages' -Force | Out-Null

Start-ScheduledTask -TaskName 'JobHunterWatch'
$waited = 0
while ((Get-ScheduledTask -TaskName 'JobHunterWatch').State -eq 'Running' -and $waited -lt 180) {
    Start-Sleep -Seconds 3
    $waited += 3
}
$info = Get-ScheduledTaskInfo -TaskName 'JobHunterWatch'
"Task created. Test run result: $($info.LastTaskResult) (0 means OK). Next run: $($info.NextRunTime)"
Get-Content (Join-Path $PSScriptRoot 'data\watch-task.log') -Encoding UTF8 -Tail 4
