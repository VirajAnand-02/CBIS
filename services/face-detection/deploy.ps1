#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy Face Detection Service

.DESCRIPTION
    Automated deployment script for the Face Detection microservice.
    Handles database migration, dependency installation, and service startup.

.PARAMETER Step
    Specific deployment step to run (all, db, deps, test, start)

.EXAMPLE
    .\deploy.ps1 -Step all
    Run full deployment

.EXAMPLE
    .\deploy.ps1 -Step db
    Run only database migration
#>

param(
    [ValidateSet('all', 'db', 'deps', 'test', 'start', 'docker')]
    [string]$Step = 'all'
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\programming\CBIS_Project"
$FaceDetectionDir = "$ProjectRoot\FACE_DETECTION"
$NextJsDir = "$ProjectRoot\next-js"

# Colors for output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-ColorOutput "`n=== $Message ===" -Color Cyan
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✓ $Message" -Color Green
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "✗ $Message" -Color Red
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠ $Message" -Color Yellow
}

# Step 1: Database Migration
function Deploy-Database {
    Write-Step "Database Migration"
    
    try {
        Set-Location $NextJsDir
        
        # Check if Prisma is installed
        if (-not (Test-Path "node_modules\.bin\prisma.cmd")) {
            Write-Warning "Prisma not found. Installing dependencies..."
            npm install
        }
        
        # Run migration
        Write-Host "Running Prisma migration..."
        npx prisma migrate dev --name add_face_recognition
        
        Write-Success "Database migration completed"
        
        # Generate Prisma Client
        Write-Host "Generating Prisma Client..."
        npx prisma generate
        
        Write-Success "Prisma Client generated"
        
    } catch {
        Write-Error "Database migration failed: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Step 2: Install Dependencies
function Deploy-Dependencies {
    Write-Step "Installing Dependencies"
    
    try {
        Set-Location $FaceDetectionDir
        
        # Check Python version
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.([0-9]+)") {
            $minorVersion = [int]$matches[1]
            if ($minorVersion -lt 8) {
                Write-Error "Python 3.8+ required. Found: $pythonVersion"
                exit 1
            }
        } else {
            Write-Error "Python 3 not found"
            exit 1
        }
        
        Write-Success "Python version: $pythonVersion"
        
        # Install requirements
        Write-Host "Installing Python packages..."
        pip install -r requirements.txt
        
        Write-Success "Dependencies installed"
        
    } catch {
        Write-Error "Dependency installation failed: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Step 3: Create Environment File
function Deploy-Environment {
    Write-Step "Environment Configuration"
    
    try {
        Set-Location $FaceDetectionDir
        
        if (-not (Test-Path ".env")) {
            Write-Host "Creating .env file from template..."
            Copy-Item ".env.example" ".env"
            
            Write-Warning "Please edit .env and set DATABASE_URL"
            Write-Host "Example: DATABASE_URL=postgresql://user:password@localhost:5432/cbis"
            
            # Ask user if they want to edit now
            $edit = Read-Host "Edit .env now? (y/n)"
            if ($edit -eq 'y') {
                notepad .env
            }
        } else {
            Write-Success ".env file already exists"
        }
        
    } catch {
        Write-Error "Environment setup failed: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Step 4: Test Service
function Deploy-Test {
    Write-Step "Testing Service"
    
    try {
        Set-Location $FaceDetectionDir
        
        # Check if service is running
        $serviceRunning = $false
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8005/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $serviceRunning = $true
            }
        } catch {
            # Service not running
        }
        
        if ($serviceRunning) {
            Write-Success "Service is already running"
            
            # Run test suite
            Write-Host "Running test suite..."
            python test_service.py
        } else {
            Write-Warning "Service is not running. Start it with: .\deploy.ps1 -Step start"
            Write-Host "You can run tests after starting the service with: python test_service.py"
        }
        
    } catch {
        Write-Error "Testing failed: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Step 5: Start Service
function Deploy-Start {
    Write-Step "Starting Service"
    
    try {
        Set-Location $FaceDetectionDir
        
        # Check if .env exists
        if (-not (Test-Path ".env")) {
            Write-Error ".env file not found. Run: .\deploy.ps1 -Step all"
            exit 1
        }
        
        # Start service
        Write-Host "Starting Face Detection Service on port 8005..."
        Write-Host "Press Ctrl+C to stop"
        Write-Host ""
        
        python app.py
        
    } catch {
        Write-Error "Failed to start service: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Step 6: Docker Deployment
function Deploy-Docker {
    Write-Step "Docker Deployment"
    
    try {
        Set-Location $ProjectRoot
        
        # Check if Docker is installed
        $dockerVersion = docker --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Docker not found. Please install Docker Desktop."
            exit 1
        }
        
        Write-Success "Docker version: $dockerVersion"
        
        # Build Docker image
        Write-Host "Building Docker image..."
        docker build -t cbis-face-detection:latest ./FACE_DETECTION
        
        Write-Success "Docker image built"
        
        # Option to start with docker-compose
        $startNow = Read-Host "Start service with docker-compose? (y/n)"
        if ($startNow -eq 'y') {
            Write-Host "Starting service..."
            docker-compose -f docker-compose.full.yml up -d face-detection
            
            Write-Success "Service started in Docker"
            Write-Host "Check logs with: docker logs cbis-face-detection -f"
        }
        
    } catch {
        Write-Error "Docker deployment failed: $_"
        exit 1
    } finally {
        Set-Location $ProjectRoot
    }
}

# Main deployment flow
function Deploy-All {
    Write-ColorOutput @"

╔═══════════════════════════════════════════════╗
║   Face Detection Service Deployment          ║
╚═══════════════════════════════════════════════╝

"@ -Color Cyan

    # Check prerequisites
    Write-Step "Checking Prerequisites"
    
    # Check Node.js
    try {
        $nodeVersion = node --version
        Write-Success "Node.js version: $nodeVersion"
    } catch {
        Write-Error "Node.js not found"
        exit 1
    }
    
    # Check Python
    try {
        $pythonVersion = python --version
        Write-Success "Python version: $pythonVersion"
    } catch {
        Write-Error "Python not found"
        exit 1
    }
    
    # Run deployment steps
    Deploy-Database
    Deploy-Dependencies
    Deploy-Environment
    
    # Summary
    Write-ColorOutput @"

╔═══════════════════════════════════════════════╗
║   Deployment Complete!                        ║
╚═══════════════════════════════════════════════╝

Next steps:
1. Edit .env file with your DATABASE_URL
2. Start the service: .\deploy.ps1 -Step start
3. Test the service: python test_service.py
4. Open API docs: http://localhost:8005/docs

"@ -Color Green
}

# Run selected step
switch ($Step) {
    'all'    { Deploy-All }
    'db'     { Deploy-Database }
    'deps'   { Deploy-Dependencies }
    'test'   { Deploy-Test }
    'start'  { Deploy-Start }
    'docker' { Deploy-Docker }
}
