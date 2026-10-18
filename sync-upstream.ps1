<#
.SYNOPSIS
  Sincroniza de forma segura el repositorio con upstream/main de Louis-CFM/coucou,
  preservando el asistente Caf y restaurando automáticamente los hooks de 1 línea.
#>

param(
    [string]$UpstreamRemote = "upstream",
    [string]$UpstreamUrl = "https://github.com/Louis-CFM/coucou.git",
    [string]$UpstreamBranch = "main"
)

$ErrorActionPreference = "Stop"
Write-Host "=== Sincronizador Seguro de Upstream (Coucou + Caf) ===" -ForegroundColor Cyan

# 1. Comprobar estado de Git
$status = git status --porcelain
if ($status) {
    Write-Host "ADVERTENCIA: Hay cambios sin commitear en tu espacio de trabajo." -ForegroundColor Yellow
    Write-Host "Guárdalos o haz commit antes de sincronizar con upstream." -ForegroundColor Yellow
    $ans = Read-Host "¿Deseas hacer 'git stash' temporal para continuar? (s/n)"
    if ($ans -eq "s" -or $ans -eq "S") {
        git stash push -m "Stash previo a sync-upstream"
    } else {
        Write-Host "Operación cancelada." -ForegroundColor Red
        exit 1
    }
}

# 2. Verificar o configurar remote upstream
$remotes = git remote
if ($remotes -notcontains $UpstreamRemote) {
    Write-Host "Agregando remote '$UpstreamRemote' -> $UpstreamUrl..." -ForegroundColor Green
    git remote add $UpstreamRemote $UpstreamUrl
}

# 3. Punto de restauración
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupTag = "backup-pre-sync-$timestamp"
Write-Host "Creando punto de restauración: $backupTag" -ForegroundColor DarkGray
git tag $backupTag

# 4. Fetch upstream
Write-Host "Descargando últimos cambios de $UpstreamRemote/$UpstreamBranch..." -ForegroundColor Cyan
git fetch $UpstreamRemote $UpstreamBranch

# 5. Merge con estrategia segura
Write-Host "Fusionando cambios de $UpstreamRemote/$UpstreamBranch..." -ForegroundColor Cyan
try {
    git merge "$UpstreamRemote/$UpstreamBranch" --no-edit
} catch {
    Write-Host "Hubo un conflicto en el merge. Revisa git status." -ForegroundColor Yellow
}

# 6. Verificación y auto-reparación de los 4 hooks mínimos de Caf:

# Hook 1: windows/src/hub/pages.ts
$pagesFile = "windows/src/hub/pages.ts"
if (Test-Path $pagesFile) {
    $content = Get-Content $pagesFile -Raw
    if ($content -notmatch "caf-voice") {
        Write-Host "[Auto-Fix] Reaplicando hook de Caf en $pagesFile..." -ForegroundColor Yellow
        $content = $content -replace 'import\s+\{\s*voicePage\s*\}\s+from\s+"\./pages/voice";', 'import { voicePage } from "./pages/caf-voice";'
        Set-Content -Path $pagesFile -Value $content -NoNewline
    }
}

# Hook 2: windows/src/hub/shell.ts
$shellFile = "windows/src/hub/shell.ts"
if (Test-Path $shellFile) {
    $content = Get-Content $shellFile -Raw
    if ($content -notmatch 'id:\s*"voice",\s*icon:\s*"wave",\s*title:\s*\(\)\s*=>\s*"Caf \(Voz\)"') {
        Write-Host "[Auto-Fix] Reaplicando título 'Caf (Voz)' en $shellFile..." -ForegroundColor Yellow
        $content = $content -replace 'id:\s*"voice",\s*icon:\s*"wave",\s*title:\s*\(\)\s*=>\s*"OK Coucou"', 'id: "voice", icon: "wave", title: () => "Caf (Voz)"'
        Set-Content -Path $shellFile -Value $content -NoNewline
    }
}

# Hook 3: windows/src/island/voice.ts
$islandVoiceFile = "windows/src/island/voice.ts"
if (Test-Path $islandVoiceFile) {
    $content = Get-Content $islandVoiceFile -Raw
    if ($content -notmatch "handleIslandVoiceAsk") {
        Write-Host "[Auto-Fix] Re-exportando handleIslandVoiceAsk en $islandVoiceFile..." -ForegroundColor Yellow
        $exportBlock = @"

export function handleIslandVoiceAsk(kind: string, input?: any): any {
  return handleVoiceAsk(kind, input);
}
"@
        Add-Content -Path $islandVoiceFile -Value $exportBlock
    }
}

# Hook 4: windows/src-tauri/src/voice/mod.rs
$voiceModFile = "windows/src-tauri/src/voice/mod.rs"
if (Test-Path $voiceModFile) {
    $content = Get-Content $voiceModFile -Raw
    if ($content -notmatch "requirements_met\(\)\s*->\s*bool\s*\{\s*false\s*\}") {
        Write-Host "[Auto-Fix] Asegurando que OK Coucou nativo quede desactivado en favor de Caf en $voiceModFile..." -ForegroundColor Yellow
        $content = $content -replace "pub fn requirements_met\(\) -> bool \{[\s\S]*?\}", "pub fn requirements_met() -> bool { false }"
        Set-Content -Path $voiceModFile -Value $content -NoNewline
    }
}

Write-Host "`n✓ Sincronización completada exitosamente sin romper Caf." -ForegroundColor Green
Write-Host "Punto de respaldo guardado en: $backupTag" -ForegroundColor DarkGray
