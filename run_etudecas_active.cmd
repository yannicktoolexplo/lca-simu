@echo off
setlocal
cd /d "%~dp0"
python etudecas\run_etudecas_pipeline.py rebuild-map-5y --open-map %*
endlocal
