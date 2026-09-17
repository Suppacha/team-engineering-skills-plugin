$ErrorActionPreference = "Stop"
& py -3.11 "$PSScriptRoot\team-update.py" install @args
exit $LASTEXITCODE
