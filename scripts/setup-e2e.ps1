# E2E Test Setup Script for Windows
# This script sets up the environment for running E2E tests

Write-Host "🚀 E2E Test Setup Script" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# Check if emulators are running
Write-Host "📡 Checking Firebase emulators..." -ForegroundColor Yellow
$authEmulator = $null
$firestoreEmulator = $null

try {
    $authEmulator = Invoke-WebRequest -Uri "http://localhost:9099" -TimeoutSec 2 -ErrorAction SilentlyContinue
} catch {}

try {
    $firestoreEmulator = Invoke-WebRequest -Uri "http://localhost:8080" -TimeoutSec 2 -ErrorAction SilentlyContinue
} catch {}

if (-not $authEmulator -or -not $firestoreEmulator) {
    Write-Host "❌ Firebase emulators are not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the emulators first:" -ForegroundColor Yellow
    Write-Host "  npm run emulators" -ForegroundColor White
    Write-Host ""
    Write-Host "Then run this script again in a new terminal." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Firebase emulators are running" -ForegroundColor Green

# Check if Angular app is running
Write-Host ""
Write-Host "🌐 Checking Angular app..." -ForegroundColor Yellow
$angularApp = $null

try {
    $angularApp = Invoke-WebRequest -Uri "http://localhost:4200" -TimeoutSec 2 -ErrorAction SilentlyContinue
} catch {}

if (-not $angularApp) {
    Write-Host "❌ Angular app is not running!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the Angular app in test mode:" -ForegroundColor Yellow
    Write-Host "  npm run start:test" -ForegroundColor White
    Write-Host ""
    Write-Host "Then run this script again in a new terminal." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Angular app is running" -ForegroundColor Green

# Seed emulator data
Write-Host ""
Write-Host "🌱 Seeding emulator data..." -ForegroundColor Yellow
node scripts/seed-emulators.mjs

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to seed emulator data" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run E2E tests:" -ForegroundColor Cyan
Write-Host "  npm run e2e:smoke     # Run smoke tests" -ForegroundColor White
Write-Host "  npm run e2e:user      # Run tests as regular user" -ForegroundColor White
Write-Host "  npm run e2e:admin     # Run tests as admin" -ForegroundColor White
Write-Host "  npm run e2e:super-admin # Run tests as super admin" -ForegroundColor White
Write-Host "  npm run e2e           # Run all tests" -ForegroundColor White
Write-Host "  npm run e2e:ui        # Run with interactive UI" -ForegroundColor White
Write-Host ""

