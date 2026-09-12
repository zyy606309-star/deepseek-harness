param(
    [Parameter(Position = 0)]
    [string]$Action,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"

$Adb = if ($env:XJB_ADB) { $env:XJB_ADB } elseif ($env:ADB) { $env:ADB } else { "adb" }
$Kp = "/data/local/tmp/kpatch"
$SuperKey = if ($env:XJB_KP_SUPERKEY) { $env:XJB_KP_SUPERKEY } else { "xiaojianbang8888" }
$KpmLocal = Join-Path $PSScriptRoot "syscallhook.kpm"
$KpatchLocal = if ($env:XJB_KPATCH_LOCAL) {
    $env:XJB_KPATCH_LOCAL
} else {
    Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) "kernelpatch-kpatch") "kpatch"
}
$KpmDev = "/data/local/tmp/scfilter.kpm"
$Name = "xiaojianbang-syscall-filter"

function Invoke-Adb {
    & $Adb @args
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-Dev {
    param([Parameter(Mandatory = $true)][string]$Command)
    & $Adb shell su -c $Command
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Show-Usage {
    Write-Host "用法: .\load.ps1 {load|unload|status|list|info|push|push-kpatch|reload|ctl <cmd>}"
    Write-Host "环境变量: XJB_ADB=C:\path\adb.exe, XJB_KP_SUPERKEY=<superkey>, XJB_KPATCH_LOCAL=C:\path\kpatch"
}

function Push-Kpatch {
    if (-not (Test-Path $KpatchLocal)) {
        Write-Error "找不到本地 kpatch: $KpatchLocal"
        exit 1
    }
    Invoke-Adb push $KpatchLocal $Kp
    Invoke-Dev "chmod 755 $Kp"
    Write-Host "kpatch pushed: $Kp"
}

function Ensure-Kpatch {
    & $Adb shell "test -x $Kp"
    if ($LASTEXITCODE -ne 0) {
        Push-Kpatch
    }
}

switch ($Action) {
    "push-kpatch" {
        Push-Kpatch
    }
    "load" {
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm load $KpmDev"
    }
    "unload" {
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm unload $Name"
    }
    "status" {
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm ctl0 $Name status >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid|_compat)?:' | tail -5"
        Write-Host ""
    }
    "list" {
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm list"
        Write-Host ""
    }
    "info" {
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm info $Name"
    }
    "ctl" {
        $CtlCommand = ($Rest -join " ")
        if (-not $CtlCommand) {
            Write-Error "ctl 需要一个无空格控制命令，例如: .\load.ps1 ctl resolve=on"
            exit 1
        }
        Ensure-Kpatch
        Invoke-Dev "$Kp $SuperKey kpm ctl0 $Name '$CtlCommand' >/dev/null"
        Invoke-Dev "dmesg | grep -E '\[scfilter\] status(_cat|_uid|_compat)?:' | tail -5"
        Write-Host ""
    }
    "push" {
        Invoke-Adb push $KpmLocal $KpmDev
        Write-Host "pushed"
    }
    "reload" {
        Ensure-Kpatch
        Invoke-Adb push $KpmLocal $KpmDev
        Invoke-Dev "$Kp $SuperKey kpm unload $Name 2>/dev/null; $Kp $SuperKey kpm load $KpmDev"
    }
    default {
        Show-Usage
        exit 1
    }
}
