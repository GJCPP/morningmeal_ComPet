# Register the fixed app for the current user's Windows sign-in.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $projectRoot 'morningmeal_Compet_V3\dist\Compet-V3'
$appExe = Join-Path $appDir 'Compet-V3.exe'
if (-not (Test-Path -LiteralPath $appExe -PathType Leaf)) {
    throw 'Build the fixed Windows app first with windows/build.ps1.'
}
$startupDir = [Environment]::GetFolderPath('Startup')
if (-not $startupDir) { throw 'Windows did not return the current user Startup directory.' }
$shortcutPath = Join-Path $startupDir 'ComPet.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -ne $appExe) {
    throw "A different ComPet startup shortcut already exists: $shortcutPath"
}
$shortcut.TargetPath = $appExe
$shortcut.WorkingDirectory = $appDir
$shortcut.IconLocation = "$appExe,0"
$shortcut.Description = 'morningmeal ComPet - start at sign-in'
$shortcut.Save()
$verified = $shell.CreateShortcut($shortcutPath)
if ($verified.TargetPath -ne $appExe -or $verified.WorkingDirectory -ne $appDir) {
    throw 'Startup shortcut validation failed.'
}
Write-Host "Startup shortcut: $shortcutPath"
Write-Host "App: $($verified.TargetPath)"
