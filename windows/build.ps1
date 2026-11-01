# Build and publish the local app to one fixed location.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This build script requires Windows.' }

$projectRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $projectRoot 'morningmeal_Compet_V3'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$buildRoot = Join-Path $appRoot 'build'
$stagingRoot = Join-Path $buildRoot 'windows-staging'
$cacheRoot = Join-Path $buildRoot 'windows-cache'
$previousDir = Join-Path $buildRoot 'windows-previous'
$distRoot = Join-Path $appRoot 'dist'
$liveDir = Join-Path $distRoot 'Compet-V3'
$liveExe = Join-Path $liveDir 'Compet-V3.exe'
$stagedDir = Join-Path $stagingRoot 'Compet-V3'
$stagedExe = Join-Path $stagedDir 'Compet-V3.exe'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'ComPet.lnk'

function Assert-ManagedPath([string]$Path) {
    $absolute = [IO.Path]::GetFullPath($Path)
    $allowedRoot = [IO.Path]::GetFullPath($appRoot).TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the app directory: $absolute"
    }
}
foreach ($path in @($stagedDir, $previousDir, $liveDir)) { Assert-ManagedPath $path }
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv. Follow windows/README.md to install build dependencies first.'
}

# Do not interrupt a running app or replace DLLs that it has loaded.
function Assert-AppStopped {
    foreach ($process in @(Get-Process -Name 'Compet-V3' -ErrorAction SilentlyContinue)) {
        $runningPath = $process.Path
        foreach ($dir in @($liveDir, $previousDir, $stagedDir)) {
            if ($runningPath -and $runningPath.StartsWith($dir + '\', [StringComparison]::OrdinalIgnoreCase)) {
                throw "ComPet is running from $dir. Exit it from its tray menu, then rebuild."
            }
        }
    }
}
Assert-AppStopped

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -ne $liveExe) {
    throw "An unrelated shortcut already exists: $shortcutPath. Rename it first."
}

New-Item -ItemType Directory -Force -Path $cacheRoot, $distRoot | Out-Null
$iconPath = Join-Path $cacheRoot 'app_icon.ico'
$originalBuildPath = $env:PATH
Push-Location $appRoot
try {
    # Prevent PyInstaller from collecting incompatible DLLs from other tools.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$(Split-Path -Parent $python)"
    & $python -c "from PIL import Image; import sys; Image.open(sys.argv[1]).convert('RGBA').save(sys.argv[2], format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" (Join-Path $appRoot 'assets\app_icon.png') $iconPath
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $python -m PyInstaller --noconfirm --onedir --windowed --name Compet-V3 `
        --distpath $stagingRoot --workpath $cacheRoot --specpath $cacheRoot `
        --add-data "$appRoot\assets;assets" --add-data "$appRoot\skins;skins" `
        --icon $iconPath (Join-Path $appRoot 'main.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed; the current app has not been replaced.' }
}
finally {
    $env:PATH = $originalBuildPath
    Pop-Location
}

& $python (Join-Path $PSScriptRoot 'smoke.py') $stagedExe
if ($LASTEXITCODE -ne 0) { throw 'Startup check failed; the current app has not been replaced.' }

# Recheck in case the app was opened while PyInstaller was working.
Assert-AppStopped

# Keep exactly one previous build for recovery. All paths are checked above.
if (Test-Path -LiteralPath $previousDir) { Remove-Item -LiteralPath $previousDir -Recurse -Force }
$backedUp = $false
$published = $false
try {
    if (Test-Path -LiteralPath $liveDir) {
        Move-Item -LiteralPath $liveDir -Destination $previousDir
        $backedUp = $true
    }
    Move-Item -LiteralPath $stagedDir -Destination $liveDir
    $published = $true
    $shortcut.TargetPath = $liveExe
    $shortcut.WorkingDirectory = $liveDir
    $shortcut.IconLocation = "$liveExe,0"
    $shortcut.Description = 'morningmeal ComPet'
    $shortcut.Save()
}
catch {
    if ($published -and (Test-Path -LiteralPath $liveDir)) {
        Move-Item -LiteralPath $liveDir -Destination $stagedDir
    }
    if ($backedUp) { Move-Item -LiteralPath $previousDir -Destination $liveDir }
    throw
}
Write-Host "App: $liveExe"
Write-Host "Desktop shortcut: $shortcutPath"
Write-Host "Previous build: $previousDir"
