// Test-only .NET Framework executable. Not shipped or called by the product.
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
public static class BridgeDiagnosticChild {
    public static int Main(string[] args) {
        if (args.Length == 1 && args[0] == "hold-child") { Thread.Sleep(20000); return 0; }
        if (args.Length < 2) return 64;
        File.WriteAllText(args[1], Process.GetCurrentProcess().Id.ToString());
        if (args[0] == "input-stall") { Thread.Sleep(20000); return 0; }
        if (args[0] == "process-stall") { Console.In.ReadToEnd(); Thread.Sleep(20000); return 0; }
        if (args[0] == "held-output") {
            var info = new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName, "hold-child");
            info.UseShellExecute = false; info.CreateNoWindow = true;
            using (var child = Process.Start(info)) {
                File.WriteAllText(args[1] + ".descendant", child.Id.ToString());
            }
            return 0;
        }
        if (args[0] == "bad-utf8") {
            var output = Console.OpenStandardOutput(); output.WriteByte(255); output.Flush(); return 0;
        }
        if (args[0] != "echo") return 65;
        var input = Console.OpenStandardInput(); var stdout = Console.OpenStandardOutput();
        input.CopyTo(stdout); stdout.Flush();
        Console.Error.Write("fixture-stderr"); return 7;
    }
}
