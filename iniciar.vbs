Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then
  MsgBox "Execute instalar.ps1 antes de iniciar o aplicativo.", 48, "Fábrica TikTok"
Else
  shell.CurrentDirectory = root
  shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\launcher.py" & Chr(34), 0, False
End If
