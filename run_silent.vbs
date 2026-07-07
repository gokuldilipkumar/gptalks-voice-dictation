' Launches GPTalks with zero visible window, regardless of the target
' executable's subsystem (the venv's pythonw.exe trampoline re-execs the
' console python.exe internally, so a plain shortcut can still flash a
' console at login -- WScript.Shell.Run's window-style 0 avoids that).
' Paths are resolved relative to this script's own location, so it works
' from any checkout.
Set fso = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = scriptDir
objShell.Run """" & scriptDir & "\.venv\Scripts\pythonw.exe"" main.py", 0, False
