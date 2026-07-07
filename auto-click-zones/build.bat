@echo off
REM Build AutoClickZones.exe using PyInstaller

echo Installing dependencies...
pip install -r requirements.txt
pip install --upgrade pyinstaller

echo Detecting Tcl/Tk data directories (works around a PyInstaller/Tkinter bundling bug)...
set "TCL_LIBRARY="
set "TK_LIBRARY="
for /f "usebackq delims=" %%i in (`python -c "import tkinter;r=tkinter.Tk();print(r.tk.call('info','library'));r.destroy()" 2^>nul`) do set "TCL_LIBRARY=%%i"
for /f "usebackq delims=" %%i in (`python -c "import tkinter;r=tkinter.Tk();print(r.tk.eval('set tk_library'));r.destroy()" 2^>nul`) do set "TK_LIBRARY=%%i"

if not defined TCL_LIBRARY (
    echo.
    echo ERROR: Could not detect TCL_LIBRARY. This usually means Tkinter itself
    echo is broken in this Python install ^(common with Microsoft Store Python
    echo or incomplete installs^). Install Python from python.org with the
    echo "tcl/tk and IDLE" option checked, then run this script again.
    pause
    exit /b 1
)
if not exist "%TCL_LIBRARY%" (
    echo.
    echo ERROR: TCL_LIBRARY was detected as "%TCL_LIBRARY%" but that folder
    echo does not exist on disk. Your Python's Tcl/Tk install looks broken.
    echo Reinstall Python from python.org with "tcl/tk and IDLE" checked.
    pause
    exit /b 1
)
echo   TCL_LIBRARY=%TCL_LIBRARY%
echo   TK_LIBRARY=%TK_LIBRARY%

echo Building executable...
pyinstaller --noconfirm --onefile --windowed ^
    --name AutoClickZones ^
    --add-data "data;data" ^
    --add-data "%TCL_LIBRARY%;_tcl_data" ^
    --add-data "%TK_LIBRARY%;_tk_data" ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=win32timezone ^
    --collect-submodules=pynput ^
    main.py

echo Copying data folder next to executable...
xcopy /E /I /Y data dist\data

echo.
echo Done! Run: dist\AutoClickZones.exe
pause
