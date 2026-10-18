Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class LaunchDesktopDaemon {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFOW {
        public int cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }
    [DllImport("kernel32.dll", EntryPoint="CreateProcessW", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool CreateProcessW(
        string lpApplicationName,
        string lpCommandLine,
        IntPtr lpProcessAttributes,
        IntPtr lpThreadAttributes,
        bool bInheritHandles,
        uint dwCreationFlags,
        IntPtr lpEnvironment,
        string lpCurrentDirectory,
        ref STARTUPINFOW lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation
    );
    [DllImport("kernel32.dll")]
    public static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

    public static void StartAndWait(string exePath, string workDir) {
        var si = new STARTUPINFOW();
        si.cb = Marshal.SizeOf(si);
        si.lpDesktop = @"Winsta0\Default";
        PROCESS_INFORMATION pi;
        bool ok = CreateProcessW(exePath, "\"" + exePath + "\"", IntPtr.Zero, IntPtr.Zero, false, 0x00000200, IntPtr.Zero, workDir, ref si, out pi);
        if (!ok) {
            Console.WriteLine("CreateProcessW failed: " + Marshal.GetLastWin32Error());
            return;
        }
        Console.WriteLine("Started PID " + pi.dwProcessId + " on Winsta0\\Default");
        WaitForSingleObject(pi.hProcess, 0xFFFFFFFF);
    }
}
"@
[LaunchDesktopDaemon]::StartAndWait("C:\Users\Joako\OneDrive\Escritorio\Coucou\windows\target\release\coucou.exe", "C:\Users\Joako\OneDrive\Escritorio\Coucou\windows")
