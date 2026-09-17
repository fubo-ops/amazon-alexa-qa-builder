param(
    [string]$Node = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
    [string]$NodeModules = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$root = Split-Path $PSScriptRoot -Parent
$temp = Join-Path $PSScriptRoot ".tmp"
$output = Join-Path $temp "output"
$rootFull = [IO.Path]::GetFullPath($root).TrimEnd([IO.Path]::DirectorySeparatorChar)
$tempFull = [IO.Path]::GetFullPath($temp)
if (-not $tempFull.StartsWith($rootFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe test temp path: $tempFull"
}

try {
    New-Item -ItemType Directory -Force -Path $output | Out-Null
    $fixtures = Join-Path $PSScriptRoot "fixtures"
    & $Python (Join-Path $root "scripts\validate_payload.py") (Join-Path $fixtures "clean_35_questions.json")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python (Join-Path $root "scripts\validate_payload.py") (Join-Path $fixtures "valid_payload_2.json")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python (Join-Path $root "scripts\export_batch.py") `
        (Join-Path $fixtures "clean_35_questions.json") `
        (Join-Path $fixtures "valid_payload_2.json") `
        --output-dir $output --max-clean-questions unlimited --node $Node --node-modules $NodeModules
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:ALEXA_QA_BATCH_OUTPUT = $output
    & $Python -m unittest discover -s $PSScriptRoot -p "test_*.py" -v
    exit $LASTEXITCODE
}
finally {
    if (Test-Path -LiteralPath $temp) {
        Remove-Item -LiteralPath $temp -Recurse -Force
    }
}
