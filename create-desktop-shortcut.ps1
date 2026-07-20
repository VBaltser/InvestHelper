# Создаёт ярлык InvestHelper на рабочем столе.
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$startBat = Join-Path $projectRoot "start.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "InvestHelper.lnk"

if (-not (Test-Path $startBat)) {
    throw "Не найден start.bat: $startBat"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $startBat
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Запуск InvestHelper (backend + frontend) и открытие в браузере"
$shortcut.Save()

Write-Host "Ярлык создан: $shortcutPath"
