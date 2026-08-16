param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$skills = Join-Path $Root 'skills'
$serverPath = Join-Path $Root 'server.py'
$failures = [System.Collections.Generic.List[string]]::new()

if (-not (Test-Path -LiteralPath $skills)) { $failures.Add("missing skills directory: $skills") }
if (-not (Test-Path -LiteralPath $serverPath)) { $failures.Add("missing server.py: $serverPath") }

if ($failures.Count -eq 0) {
    $serverText = Get-Content -Raw -LiteralPath $serverPath -Encoding UTF8
    $registered = [regex]::Matches($serverText, '_tool\(\s*"([a-zA-Z0-9_]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    $dispatched = [regex]::Matches($serverText, 'name\s*==\s*"([a-zA-Z0-9_]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique

    foreach ($name in $registered) {
        if ($name -notin $dispatched) { $failures.Add("registered tool has no call_tool branch: $name") }
    }
    foreach ($name in $dispatched) {
        if ($name -notin $registered) { $failures.Add("call_tool branch is not registered: $name") }
    }

    $browserDoc = Get-ChildItem -LiteralPath $skills -File -Filter '01_*.md' | Select-Object -First 1 -ExpandProperty FullName
    if (-not $browserDoc) { $failures.Add('missing browser control skill document') }
    if ($browserDoc) {
    $documented = [regex]::Matches((Get-Content -Raw -LiteralPath $browserDoc -Encoding UTF8), '(?m)^### `([^`]+)`') |
        ForEach-Object { $_.Groups[1].Value -split '\s*/\s*' } |
        ForEach-Object { $_.Trim() } | Sort-Object -Unique

    foreach ($name in $documented) {
        if ($name -notin $registered) { $failures.Add("browser doc tool is not registered: $name") }
    }
    }

    Get-ChildItem -LiteralPath $skills -File -Filter '*.md' | ForEach-Object {
        $text = Get-Content -Raw -LiteralPath $_.FullName -Encoding UTF8
        $fences = (Select-String -InputObject $text -Pattern '^```' -AllMatches | Measure-Object).Count
        if (($fences % 2) -ne 0) { $failures.Add("odd markdown fence count: $($_.Name)") }

        foreach ($match in [regex]::Matches($text, '\]\((/?D:/[^)]+)\)')) {
            $path = $match.Groups[1].Value -replace '^/', '' -replace '/', '\'
            if (-not (Test-Path -LiteralPath $path)) { $failures.Add("broken local link in $($_.Name): $path") }
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "skill documentation validation passed: $skills"
