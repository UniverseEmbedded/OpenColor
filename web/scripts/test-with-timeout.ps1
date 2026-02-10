# 自动化测试脚本 - 带超时控制
# 用于运行所有测试并在超时时自动退出

param(
    [int]$TimeoutMinutes = 10,
    [switch]$SkipRust,
    [switch]$SkipUnit,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$startTime = Get-Date
$timeout = New-TimeSpan -Minutes $TimeoutMinutes

function Write-Header($message) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $message" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "✓ $message" -ForegroundColor Green
}

function Write-Error($message) {
    Write-Host "✗ $message" -ForegroundColor Red
}

function Write-Warning($message) {
    Write-Host "⚠ $message" -ForegroundColor Yellow
}

function Test-Timeout {
    $elapsed = New-TimeSpan -Start $startTime -End (Get-Date)
    if ($elapsed -gt $timeout) {
        Write-Error "测试超时！已运行 $($elapsed.TotalMinutes.ToString('F1')) 分钟"
        exit 1
    }
}

function Run-CommandWithTimeout {
    param(
        [string]$Command,
        [string]$Arguments,
        [string]$WorkingDirectory = ".",
        [int]$CommandTimeoutMinutes = 10
    )
    
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Command
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    
    # 收集输出
    $stdout = New-Object System.Text.StringBuilder
    $stderr = New-Object System.Text.StringBuilder
    
    $outputHandler = {
        if ($EventArgs.Data) {
            $stdout.AppendLine($EventArgs.Data) | Out-Null
            if ($Verbose) {
                Write-Host $EventArgs.Data
            }
        }
    }
    
    $errorHandler = {
        if ($EventArgs.Data) {
            $stderr.AppendLine($EventArgs.Data) | Out-Null
            if ($Verbose) {
                Write-Host $EventArgs.Data -ForegroundColor Red
            }
        }
    }
    
    $outEvent = Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action $outputHandler
    $errEvent = Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action $errorHandler
    
    $process.Start() | Out-Null
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    
    # 等待进程完成或超时
    $commandTimeout = New-TimeSpan -Minutes $CommandTimeoutMinutes
    $commandStart = Get-Date
    
    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 100
        
        $commandElapsed = New-TimeSpan -Start $commandStart -End (Get-Date)
        if ($commandElapsed -gt $commandTimeout) {
            Write-Error "命令执行超时！"
            $process.Kill()
            return @{ Success = $false; ExitCode = -1; Output = $stdout.ToString(); Error = $stderr.ToString() }
        }
        
        Test-Timeout
    }
    
    # 等待事件处理完成
    Start-Sleep -Milliseconds 500
    
    Unregister-Event -SourceIdentifier $outEvent.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $errEvent.Name -ErrorAction SilentlyContinue
    
    return @{
        Success = $process.ExitCode -eq 0
        ExitCode = $process.ExitCode
        Output = $stdout.ToString()
        Error = $stderr.ToString()
    }
}

# 主程序
Write-Header "OpenColor Web 自动化测试"
Write-Host "超时设置: $TimeoutMinutes 分钟"
Write-Host "开始时间: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host ""

$results = @{
    Unit = $null
    Rust = $null
}

# 单元测试
if (-not $SkipUnit) {
    Write-Header "运行单元测试 (Vitest)"
    Test-Timeout
    
    $result = Run-CommandWithTimeout -Command "pnpm" -Arguments "run test:unit" -CommandTimeoutMinutes 5
    $results.Unit = $result
    
    if ($result.Success) {
        Write-Success "单元测试通过"
    } else {
        Write-Error "单元测试失败"
        if ($result.Error) {
            Write-Host $result.Error -ForegroundColor Red
        }
    }
} else {
    Write-Warning "跳过单元测试"
}

# Rust 测试
if (-not $SkipRust) {
    Write-Header "运行 Rust 后端测试"
    Test-Timeout
    
    $result = Run-CommandWithTimeout -Command "cargo" -Arguments "test" -WorkingDirectory "src-tauri" -CommandTimeoutMinutes 5
    $results.Rust = $result
    
    if ($result.Success) {
        Write-Success "Rust 测试通过"
    } else {
        Write-Error "Rust 测试失败"
        if ($result.Error) {
            Write-Host $result.Error -ForegroundColor Red
        }
    }
} else {
    Write-Warning "跳过 Rust 测试"
}

# 汇总结果
Write-Header "测试结果汇总"

$endTime = Get-Date
$totalDuration = New-TimeSpan -Start $startTime -End $endTime

$allPassed = $true

if (-not $SkipUnit) {
    $status = if ($results.Unit.Success) { "通过 ✓" } else { "失败 ✗" }
    Write-Host "单元测试: $status" -ForegroundColor $(if ($results.Unit.Success) { "Green" } else { "Red" })
    $allPassed = $allPassed -and $results.Unit.Success
}

if (-not $SkipRust) {
    $status = if ($results.Rust.Success) { "通过 ✓" } else { "失败 ✗" }
    Write-Host "Rust 测试: $status" -ForegroundColor $(if ($results.Rust.Success) { "Green" } else { "Red" })
    $allPassed = $allPassed -and $results.Rust.Success
}

Write-Host ""
Write-Host "总耗时: $($totalDuration.ToString('hh\:mm\:ss'))"

if ($allPassed) {
    Write-Success "所有测试通过！"
    exit 0
} else {
    Write-Error "部分测试失败"
    exit 1
}
