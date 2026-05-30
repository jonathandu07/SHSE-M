param(
    [string]$Root = "C:\Users\alpha\Documents\GitHub\SHSE-M\frontend",
    [int]$MaxDepth = 8,
    [string]$Output = "C:\Users\alpha\Documents\GitHub\SHSE-M\frontend_architecture.md"
)

$ErrorActionPreference = "Stop"

$ExcludedDirs = @(
    ".git", ".idea", ".vscode",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".kivy", "node_modules", "dist", "build", "coverage", "htmlcov",
    "logs", "tmp", "temp", ".venv", "venv", "env"
)

$InterestingExtensions = @(
    ".py", ".kv", ".json", ".md", ".txt", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".js", ".ts", ".jsx", ".tsx", ".vue",
    ".css", ".scss", ".html"
)

function Test-IsExcludedPath {
    param([string]$Path)

    foreach ($part in ($Path -split "[\\/]")) {
        if ($ExcludedDirs -contains $part) {
            return $true
        }
    }

    return $false
}

function Get-RelativePath {
    param(
        [string]$BasePath,
        [string]$FullPath
    )

    $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\') + '\'
    $full = [System.IO.Path]::GetFullPath($FullPath)

    if ($full.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $full.Substring($base.Length)
    }

    return $full
}

function Get-Depth {
    param([string]$RelativePath)

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return 0
    }

    return ($RelativePath -split "[\\/]").Count
}

function Write-Tree {
    param(
        [System.IO.DirectoryInfo]$Directory,
        [int]$Depth = 0
    )

    if ($Depth -gt $MaxDepth) {
        return
    }

    $items = Get-ChildItem -LiteralPath $Directory.FullName -Force |
        Where-Object { -not (Test-IsExcludedPath $_.FullName) } |
        Sort-Object @{ Expression = { -not $_.PSIsContainer } }, Name

    foreach ($item in $items) {
        $relative = Get-RelativePath -BasePath $Root -FullPath $item.FullName
        $level = Get-Depth -RelativePath $relative

        if ($level -gt $MaxDepth) {
            continue
        }

        $indent = "  " * $Depth

        if ($item.PSIsContainer) {
            Add-Content -LiteralPath $Output -Value "$indent- [DIR] $($item.Name)/"
            Write-Tree -Directory $item -Depth ($Depth + 1)
        }
        else {
            Add-Content -LiteralPath $Output -Value "$indent- [FILE] $($item.Name)"
        }
    }
}

if (-not (Test-Path -LiteralPath $Root)) {
    throw "Le dossier frontend n'existe pas : $Root"
}

if (Test-Path -LiteralPath $Output) {
    Remove-Item -LiteralPath $Output -Force
}

$allFiles = Get-ChildItem -LiteralPath $Root -Recurse -File -Force |
    Where-Object { -not (Test-IsExcludedPath $_.FullName) }

$interestingFiles = $allFiles |
    Where-Object { $InterestingExtensions -contains $_.Extension.ToLowerInvariant() } |
    Sort-Object FullName

$totalSizeMb = [Math]::Round((($allFiles | Measure-Object Length -Sum).Sum / 1MB), 3)

Add-Content -LiteralPath $Output -Value "# Architecture frontend STHO-ME / SHSE-M"
Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "Racine analysée : ``$Root``"
Add-Content -LiteralPath $Output -Value "Date export : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "## Résumé"
Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "- Nombre total de fichiers : $($allFiles.Count)"
Add-Content -LiteralPath $Output -Value "- Nombre de fichiers utiles listés : $($interestingFiles.Count)"
Add-Content -LiteralPath $Output -Value "- Taille totale approximative : $totalSizeMb Mo"
Add-Content -LiteralPath $Output -Value "- Profondeur maximale exportée : $MaxDepth"
Add-Content -LiteralPath $Output -Value ""

Add-Content -LiteralPath $Output -Value "## Arborescence"
Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "- [DIR] frontend/"
Write-Tree -Directory (Get-Item -LiteralPath $Root) -Depth 1
Add-Content -LiteralPath $Output -Value ""

Add-Content -LiteralPath $Output -Value "## Répartition par extension"
Add-Content -LiteralPath $Output -Value ""

$allFiles |
    Group-Object Extension |
    Sort-Object Count -Descending |
    ForEach-Object {
        $ext = if ([string]::IsNullOrWhiteSpace($_.Name)) { "[sans extension]" } else { $_.Name }
        Add-Content -LiteralPath $Output -Value "- ``$ext`` : $($_.Count)"
    }

Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "## Liste complète des fichiers utiles"
Add-Content -LiteralPath $Output -Value ""

foreach ($file in $interestingFiles) {
    $relative = Get-RelativePath -BasePath $Root -FullPath $file.FullName
    $sizeKb = [Math]::Round($file.Length / 1KB, 2)
    Add-Content -LiteralPath $Output -Value "- ``$relative`` — $sizeKb Ko"
}

Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "## Fichiers probablement importants"
Add-Content -LiteralPath $Output -Value ""

$importantPatterns = @(
    "main.py",
    "components.py",
    "dashboard.py",
    "report_adapter.py",
    "raw_report_view.py",
    "system_data.py",
    "missing_requirements.py",
    "frontend_contract.py",
    "package.json",
    "vite.config.js",
    "vite.config.ts",
    "tailwind.config.js",
    "tailwind.config.ts"
)

foreach ($pattern in $importantPatterns) {
    $matches = $interestingFiles | Where-Object { $_.Name -ieq $pattern }

    foreach ($match in $matches) {
        $relative = Get-RelativePath -BasePath $Root -FullPath $match.FullName
        Add-Content -LiteralPath $Output -Value "- ``$relative``"
    }
}

Add-Content -LiteralPath $Output -Value ""
Add-Content -LiteralPath $Output -Value "## Aperçu rapide des fichiers Python"
Add-Content -LiteralPath $Output -Value ""

$pythonFiles = $interestingFiles | Where-Object { $_.Extension -ieq ".py" }

foreach ($file in $pythonFiles) {
    $relative = Get-RelativePath -BasePath $Root -FullPath $file.FullName

    Add-Content -LiteralPath $Output -Value "### ``$relative``"
    Add-Content -LiteralPath $Output -Value ""

    $content = Get-Content -LiteralPath $file.FullName -TotalCount 120 -ErrorAction SilentlyContinue

    $imports = $content |
        Select-String -Pattern "^\s*(from\s+.+\s+import\s+.+|import\s+.+)" |
        ForEach-Object { $_.Line.Trim() }

    $classes = $content |
        Select-String -Pattern "^\s*class\s+[A-Za-z_][A-Za-z0-9_]*" |
        ForEach-Object { $_.Line.Trim() }

    $functions = $content |
        Select-String -Pattern "^\s*def\s+[A-Za-z_][A-Za-z0-9_]*" |
        ForEach-Object { $_.Line.Trim() }

    if ($imports.Count -gt 0) {
        Add-Content -LiteralPath $Output -Value "**Imports principaux :**"
        foreach ($line in ($imports | Select-Object -First 15)) {
            Add-Content -LiteralPath $Output -Value "- ``$line``"
        }
        Add-Content -LiteralPath $Output -Value ""
    }

    if ($classes.Count -gt 0) {
        Add-Content -LiteralPath $Output -Value "**Classes détectées :**"
        foreach ($line in $classes) {
            Add-Content -LiteralPath $Output -Value "- ``$line``"
        }
        Add-Content -LiteralPath $Output -Value ""
    }

    if ($functions.Count -gt 0) {
        Add-Content -LiteralPath $Output -Value "**Fonctions détectées :**"
        foreach ($line in ($functions | Select-Object -First 30)) {
            Add-Content -LiteralPath $Output -Value "- ``$line``"
        }
        Add-Content -LiteralPath $Output -Value ""
    }
}

Write-Host ""
Write-Host "Export terminé :" -ForegroundColor Green
Write-Host $Output -ForegroundColor Cyan
Write-Host ""
Write-Host "Colle-moi ensuite le contenu de frontend_architecture.md." -ForegroundColor Yellow
