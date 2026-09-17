$ErrorActionPreference = "Stop"
# Select an available Python 3; the entry point enforces the 3.11+ minimum.
& py -3 "$PSScriptRoot\team-update.py" install @args
exit $LASTEXITCODE
