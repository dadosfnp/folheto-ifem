<#
.SYNOPSIS
    Publica os PDFs de output/ como assets de um GitHub Release.

.DESCRIPTION
    Por que existe em vez de um `gh release create output/*.pdf` direto:

    1. O PowerShell nao expande globs para executaveis nativos, e o cmd.exe nao
       expande glob nenhum. O comando "obvio" falha silenciosamente com
       "no matches found".
    2. Mesmo expandindo, 424 caminhos completos passam de 38 mil caracteres e
       estouram o limite de 32.767 da linha de comando do Windows.

    Este script cria o release vazio e sobe os arquivos em lotes, com retry por
    lote — um upload de ~1,4 GB derrubado no meio nao deve exigir recomecar tudo.

.EXAMPLE
    .\tools\publicar_release.ps1 -Tag v2 -Titulo "Folhetos IFEM 2025"
    .\tools\publicar_release.ps1 -Tag v2 -Retomar     # sobe so o que falta
#>
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Titulo = "Folhetos IFEM",
    [string]$Notas = "",
    [int]$TamanhoLote = 40,
    [switch]$Retomar,
    [switch]$DryRun
)

# Deliberadamente NAO usa ErrorActionPreference='Stop': no PowerShell 5.1 isso
# transforma qualquer linha de stderr de um executavel nativo em erro terminante,
# e `gh release view` escreve "release not found" no stderr como resposta NORMAL
# quando a tag ainda nao existe — que e justamente o caso comum aqui.
# O controle de erro e feito por $LASTEXITCODE, explicitamente.
$ErrorActionPreference = "Continue"
$raiz = Split-Path $PSScriptRoot -Parent
$repo = "dadosfnp/folheto-ifem"

function Parar($msg) {
    Write-Host $msg -ForegroundColor Red
    exit 1
}

$pdfs = Get-ChildItem (Join-Path $raiz "output") -Filter "*.pdf" -File
if ($pdfs.Count -eq 0) { Parar "Nenhum PDF em output/" }

$totalMB = [math]::Round(($pdfs | Measure-Object -Property Length -Sum).Sum / 1MB, 0)
Write-Host "Release: $Tag  |  $($pdfs.Count) PDFs  |  $totalMB MB"

# Release ja existe?
gh release view $Tag --repo $repo *> $null
$existe = ($LASTEXITCODE -eq 0)

if ($existe -and -not $Retomar) {
    Parar "Release '$Tag' ja existe. Use -Retomar para completar o upload, ou escolha outra tag."
}

if ($Retomar) {
    if (-not $existe) { Parar "Release '$Tag' nao existe - rode sem -Retomar primeiro." }
    Write-Host "Modo retomar: conferindo o que ja subiu..."
    $jaSubiu = (gh release view $Tag --repo $repo --json assets --jq '.assets[].name') -split "`n" |
               Where-Object { $_ }
    $pdfs = $pdfs | Where-Object { $jaSubiu -notcontains $_.Name }
    Write-Host "  ja no release: $($jaSubiu.Count)  |  faltando: $($pdfs.Count)"
    if ($pdfs.Count -eq 0) { Write-Host "Nada a fazer."; exit 0 }
}

if ($DryRun) {
    Write-Host "`n[dry-run] criaria o release e subiria $($pdfs.Count) arquivo(s) em $([math]::Ceiling($pdfs.Count / $TamanhoLote)) lote(s)."
    exit 0
}

if (-not $existe) {
    Write-Host "`nCriando o release (sem arquivos)..."
    if ([string]::IsNullOrWhiteSpace($Notas)) {
        gh release create $Tag --repo $repo --title $Titulo --notes "Lote de folhetos IFEM."
    } else {
        gh release create $Tag --repo $repo --title $Titulo --notes $Notas
    }
    if ($LASTEXITCODE -ne 0) { Parar "Falha ao criar o release." }
}

# Upload em lotes: contorna o limite de linha de comando e permite retry pontual.
$lotes = [math]::Ceiling($pdfs.Count / $TamanhoLote)
$enviados = 0
$falhas = @()

for ($i = 0; $i -lt $pdfs.Count; $i += $TamanhoLote) {
    $lote = $pdfs[$i..([math]::Min($i + $TamanhoLote - 1, $pdfs.Count - 1))]
    $n = [math]::Floor($i / $TamanhoLote) + 1
    $mb = [math]::Round(($lote | Measure-Object -Property Length -Sum).Sum / 1MB, 0)
    Write-Host "  lote $n/$lotes  ($($lote.Count) arquivos, $mb MB)..." -NoNewline

    $caminhos = $lote | ForEach-Object { $_.FullName }
    gh release upload $Tag @caminhos --repo $repo --clobber *> $null

    if ($LASTEXITCODE -eq 0) {
        $enviados += $lote.Count
        Write-Host " ok"
    } else {
        $falhas += $n
        Write-Host " FALHOU" -ForegroundColor Red
    }
}

Write-Host "`n------------------------------------------------------------"
Write-Host "Enviados: $enviados / $($pdfs.Count)"
if ($falhas.Count -gt 0) {
    Write-Host "Lotes com falha: $($falhas -join ', ')" -ForegroundColor Red
    Write-Host "Rode de novo com -Retomar para completar."
    exit 1
}
Write-Host "Release publicado: https://github.com/$repo/releases/tag/$Tag"
