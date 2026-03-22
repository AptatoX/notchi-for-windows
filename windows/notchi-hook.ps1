$ErrorActionPreference = "SilentlyContinue"
$appDir = "__NOTCHI_APP_DIR__"

function Send-NotchiPayload {
    param(
        [string]$JsonPayload
    )

    $client = [System.Net.Sockets.TcpClient]::new("127.0.0.1", 8765)
    $stream = $client.GetStream()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($JsonPayload)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Dispose()
    $client.Dispose()
}

function Start-NotchiApp {
    if ([string]::IsNullOrWhiteSpace($appDir)) {
        return $false
    }

    $appPath = Join-Path $appDir "app.py"
    if (-not (Test-Path $appPath)) {
        return $false
    }

    $candidates = @("pythonw", "pyw", "python", "py")
    foreach ($name in $candidates) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        $arguments = @()
        if ($name -eq "py" -or $name -eq "pyw") {
            $arguments += "-3"
        }
        $arguments += "`"$appPath`""

        Start-Process -FilePath $command.Source -ArgumentList $arguments -WindowStyle Hidden | Out-Null
        return $true
    }

    return $false
}

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payload)) {
    exit 0
}

try {
    $inputObject = $payload | ConvertFrom-Json
} catch {
    exit 0
}

$statusMap = @{
    "UserPromptSubmit" = "processing"
    "PreCompact" = "compacting"
    "SessionStart" = "waiting_for_input"
    "SessionEnd" = "ended"
    "PreToolUse" = "running_tool"
    "PostToolUse" = "processing"
    "PermissionRequest" = "waiting_for_input"
    "Stop" = "waiting_for_input"
    "SubagentStop" = "waiting_for_input"
}

$output = @{
    session_id = $inputObject.session_id
    cwd = $inputObject.cwd
    event = $inputObject.hook_event_name
    status = if ($inputObject.status) { $inputObject.status } else { $statusMap[$inputObject.hook_event_name] }
    interactive = $true
    permission_mode = if ($inputObject.permission_mode) { $inputObject.permission_mode } else { "default" }
}

if ($inputObject.prompt) {
    $output.user_prompt = $inputObject.prompt
}

if ($inputObject.tool_name) {
    $output.tool = $inputObject.tool_name
}

if ($inputObject.tool_use_id) {
    $output.tool_use_id = $inputObject.tool_use_id
}

if ($inputObject.tool_input) {
    $output.tool_input = $inputObject.tool_input
}

$jsonPayload = $output | ConvertTo-Json -Depth 8 -Compress

try {
    Send-NotchiPayload -JsonPayload $jsonPayload
    exit 0
} catch {
}

if (Start-NotchiApp) {
    Start-Sleep -Milliseconds 1200
    try {
        Send-NotchiPayload -JsonPayload $jsonPayload
        exit 0
    } catch {
    }
}
