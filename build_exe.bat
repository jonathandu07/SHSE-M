@echo off
echo PREPARATION DE L'ENVIRONNEMENT...
pip install --upgrade pyinstaller

echo NETTOYAGE...
rmdir /s /q build
rmdir /s /q dist
del *.spec

echo COMPILATION...
pyinstaller --noconfirm --onefile --windowed ^
    --name "SHSE_Dimensionnement" ^
    --hidden-import=tkinter ^
    --hidden-import=matplotlib ^
    shse_m_sizing/gui.py

echo TERMINE!
echo L'executable est dans le dossier 'dist/'.
pause
