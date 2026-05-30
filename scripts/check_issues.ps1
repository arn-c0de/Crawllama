try {
    $results = Get-Content 'd:\Artificial-Intelligent\Crawllama\codeql-results.sarif' | ConvertFrom-Json
    $critical = $results.runs[0].results | Where-Object {$_.level -eq 'error' -and $_.ruleId -ne 'py/weak-sensitive-data-hashing' -and $_.locations[0].physicalLocation.artifactLocation.uri -notmatch 'tests/'}
    $count = $critical.Count
    "DEBUG: Found $count" | Out-File debug_check_issues.log -Encoding utf8
    if ($count -eq 0) {
        Write-Host "Found 0 critical issues (excluding weak-hashing for rate limiting):"
        exit 0
    }
    Write-Host "Found $count critical issues (excluding weak-hashing for rate limiting):"
    $critical | ForEach-Object {
        Write-Host "- $($_.ruleId) in $($_.locations[0].physicalLocation.artifactLocation.uri) at line $($_.locations[0].physicalLocation.region.startLine)"
        "- $($_.ruleId) in $($_.locations[0].physicalLocation.artifactLocation.uri) at line $($_.locations[0].physicalLocation.region.startLine)" | Out-File debug_check_issues.log -Append -Encoding utf8
    }
    exit 1
} catch {
    "ERROR: $_" | Out-File debug_check_issues.log -Append -Encoding utf8
    exit 2
}
