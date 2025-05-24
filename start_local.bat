@echo off
echo Starting CommunityVoice Application...

:: Start the server
start cmd /k "cd server && python app.py"

:: Wait for 2 seconds to let the server start
timeout /t 2

:: Start the client (opening index.html in default browser)
start http://localhost:5000

echo Application started successfully!
echo Server running at http://localhost:5000
echo Press any key to exit...
pause > nul 