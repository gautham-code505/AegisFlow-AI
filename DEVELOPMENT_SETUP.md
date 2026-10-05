# AegisFlow AI — Development Environment Setup

This document outlines how to set up the local development environment for the AegisFlow AI project on Windows.

## 1. Prerequisites
- **Python Version**: Python 3.13 (64-bit) is required for this environment.
- **Node.js**: Required for the frontend dashboard build.

## 2. Python Virtual Environment Setup

### Create the Virtual Environment
Open PowerShell and navigate to the project directory, then create a virtual environment:
```powershell
cd c:\project
python -m venv .venv
```

### Activate the Virtual Environment
```powershell
.venv\Scripts\Activate.ps1
```
*(Note: If execution policies block the activation script, you may need to run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` first, or directly use the `.venv\Scripts\python.exe` executable.)*

### Install Project Dependencies
With the virtual environment activated:
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Validating the Environment

### Backend Import Check
Before running tests, verify that the core backend modules can be imported successfully:
```powershell
python -c "import backend.app; print('IMPORT_OK')"
```

### Running Backend Tests
The backend test suite is powered by `pytest`. Run it via:
```powershell
python -m pytest tests\backend -v
python -m pytest tests\vision -v
```
*Note: If your Windows system uses strict Application Control policies (e.g., AppLocker), binary machine-learning dependencies like `torch_global_deps.dll` may fail to load. This will block backend execution entirely until an exception or bypass is configured.*

## 4. Frontend Build
To compile the digital twin dashboard frontend:
```powershell
cd c:\project\frontend
npm run build
```
