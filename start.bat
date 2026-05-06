@echo off
echo Uruchamianie Polish Bank B...
echo.


docker compose up --build -d
docker compose up --build 

echo.
echo Czekam az serwisy beda gotowe...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo  Polish Bank B - gotowe!
echo ========================================
echo.
echo  Frontend:    http://localhost:4200
echo  Backend API: http://localhost:8000/api/
echo  Swagger UI:  http://localhost:8000/api/schema/swagger-ui/
echo  Admin:       http://localhost:8000/admin/
echo.
echo ========================================
echo.

start http://localhost:4200
