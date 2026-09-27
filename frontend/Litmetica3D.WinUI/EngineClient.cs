using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace Litmetica3D.WinUI;

// No command shell: every path and argument is passed independently to Python.
public sealed class EngineClient : IDisposable
{
    private Process? process;
    public static string FindRoot()
    {
        foreach (var start in new[] { AppContext.BaseDirectory, Environment.CurrentDirectory })
            for (var directory = new DirectoryInfo(start); directory != null; directory = directory.Parent)
                if (File.Exists(Path.Combine(directory.FullName, "litmetica3d", "winui_bridge.py")))
                    return directory.FullName;
        throw new DirectoryNotFoundException("未找到转换引擎。请从仓库启动，或将 litmetica3d 文件夹放在程序旁。");
    }

    public async Task RunAsync(string python, object request, Action<JsonElement> receive, CancellationToken token)
    {
        var root = FindRoot();
        if (string.IsNullOrWhiteSpace(python))
        {
            var bundled = Path.Combine(root, "runtime", "python", "python.exe");
            var local = Path.Combine(root, ".venv", "Scripts", "python.exe");
            python = File.Exists(bundled) ? bundled : File.Exists(local) ? local : "python.exe";
        }
        var start = new ProcessStartInfo(python)
        {
            WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false), StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        start.ArgumentList.Add("-u");
        start.ArgumentList.Add("-m");
        start.ArgumentList.Add("litmetica3d.winui_bridge");
        start.Environment["PYTHONUTF8"] = "1";
        process = new Process { StartInfo = start };
        var active = process;
        // Keep process startup and pipe handling off the XAML dispatcher. When
        // ReadLineAsync completes synchronously on a buffered stream, capturing
        // the UI context can otherwise starve input and elapsed-time updates.
        if (!await Task.Run(active.Start).ConfigureAwait(false))
            throw new InvalidOperationException("无法启动转换引擎。");
        var stderr = new StringBuilder();
        var errors = Task.Run(async () =>
        {
            while (await active.StandardError.ReadLineAsync().ConfigureAwait(false) is { } line)
            {
                if (stderr.Length > 16000) stderr.Remove(0, 8000);
                stderr.AppendLine(line);
            }
        });
        await active.StandardInput.WriteLineAsync(JsonSerializer.Serialize(request)).ConfigureAwait(false);
        await active.StandardInput.FlushAsync().ConfigureAwait(false);
        using var registration = token.Register(() => _ = CancelAsync(active));
        var terminal = false;
        string? failure = null;
        var progressClock = Stopwatch.StartNew();
        var lastProgressAt = -1000L;
        string? lastStage = null;
        JsonElement? pendingProgress = null;
        while (await active.StandardOutput.ReadLineAsync().ConfigureAwait(false) is { } line)
        {
            using var json = JsonDocument.Parse(line);
            var item = json.RootElement.Clone();
            var kind = item.GetProperty("type").GetString();
            if (kind == "progress")
            {
                pendingProgress = item;
                var stage = item.TryGetProperty("stage", out var value) ? value.GetString() : null;
                var now = progressClock.ElapsedMilliseconds;
                if (stage != lastStage || now - lastProgressAt >= 150)
                {
                    receive(item);
                    pendingProgress = null;
                    lastProgressAt = now;
                    lastStage = stage;
                }
                continue;
            }
            if (pendingProgress is { } latest)
            {
                receive(latest);
                pendingProgress = null;
            }
            if (kind is "complete" or "cancelled" or "error") terminal = true;
            if (kind == "error") failure = item.GetProperty("text").GetString();
            receive(item);
        }
        if (pendingProgress is { } finalProgress) receive(finalProgress);
        await active.WaitForExitAsync().ConfigureAwait(false);
        await errors.ConfigureAwait(false);
        if (failure != null) throw new InvalidOperationException(failure);
        if (!terminal && token.IsCancellationRequested) throw new OperationCanceledException(token);
        if (!terminal || active.ExitCode != 0)
            throw new InvalidOperationException($"转换进程退出（{active.ExitCode}）。请检查 Python 依赖。\n{stderr}");
    }

    private static async Task CancelAsync(Process active)
    {
        try
        {
            if (active.HasExited) return;
            await active.StandardInput.WriteLineAsync("{\"command\":\"cancel\"}").ConfigureAwait(false);
            await active.StandardInput.FlushAsync().ConfigureAwait(false);
            // A native boolean operation may not reach a cancellation checkpoint.
            await Task.WhenAny(active.WaitForExitAsync(), Task.Delay(5000)).ConfigureAwait(false);
            if (!active.HasExited) active.Kill(entireProcessTree: true);
        }
        catch (Exception ex) when (ex is InvalidOperationException or IOException or System.ComponentModel.Win32Exception) { }
    }

    public void Dispose()
    {
        if (process is { } active)
        {
            try { if (!active.HasExited) active.Kill(entireProcessTree: true); }
            catch (InvalidOperationException) { }
            process.Dispose();
            process = null;
        }
    }
}
