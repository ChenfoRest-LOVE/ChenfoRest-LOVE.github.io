[CmdletBinding()]
param([switch]$Rollback, [string]$Revision)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
function Check-Native([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)" }
}
if ($Rollback) {
    & ssh -o BatchMode=yes xmu-server 'sudo -n /usr/local/sbin/chenforest-activate --rollback'
    Check-Native 'Rollback'
    exit 0
}
& git -C $repo fetch origin main
Check-Native 'Fetch origin/main'
$remoteRevision = (& git -C $repo rev-parse origin/main).Trim()
Check-Native 'Resolve revision'
$releaseRevision = $remoteRevision
if ($Revision) {
    if ($Revision -notmatch '^[0-9a-f]{40}$') { throw 'Expected a full Git revision' }
    if ($Revision -ne $remoteRevision) { throw 'origin/main changed after the approved revision; refresh and retry publication.' }
    $releaseRevision = $Revision
}
if ($releaseRevision -notmatch '^[0-9a-f]{40}$') { throw 'Invalid origin/main revision' }
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('chenforest-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $archive = Join-Path $temporary ($releaseRevision + '.tar')
    & git -C $repo archive --format=tar "--output=$archive" $releaseRevision index.html photos.html writing.html reading.html projects.html assets content
    Check-Native 'Build Git archive'
    & ssh -o BatchMode=yes xmu-server 'install -d -m 700 /home/ubuntu/site-deploy/incoming'
    Check-Native 'Prepare incoming directory'
    & scp -o BatchMode=yes $archive "xmu-server:/home/ubuntu/site-deploy/incoming/$releaseRevision.tar"
    Check-Native 'Upload release'
    & ssh -o BatchMode=yes xmu-server "sudo -n /usr/local/sbin/chenforest-activate $releaseRevision"
    Check-Native 'Activate release'
    $active = ((& ssh -o BatchMode=yes xmu-server 'curl --fail --silent http://127.0.0.1/__revision') -join "`n").Trim()
    Check-Native 'Verify active release'
    if ($active -ne $releaseRevision) { throw "Active revision differs: $active" }
    Write-Host "Published origin/main: $releaseRevision"
} finally {
    # Delete only the exact temporary archive and its now-empty owned directory.
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
    Remove-Item -LiteralPath $temporary
}
