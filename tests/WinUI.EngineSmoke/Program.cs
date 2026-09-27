using System.Text.Json;
using Litmetica3D.WinUI;

if (args.Length != 1 || !File.Exists(args[0]))
    throw new ArgumentException("Pass the path to a small .litematic test fixture.");
var source = Path.GetFullPath(args[0]);
var output = Path.Combine(Path.GetTempPath(), "litmetica3d-client-" + Guid.NewGuid());
try
{
    var request = new { files = new[] { source }, output_dir = output,
        options = new { output_format = "stl", geometry = "print", components = "main", cavities = "fill" } };
    var events = new List<JsonElement>();
    using (var client = new EngineClient())
    using (var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30)))
        await client.RunAsync("", request, events.Add, timeout.Token);
    if (!events.Any(x => x.GetProperty("type").GetString() == "progress")) throw new Exception("Missing progress");
    if (events[^1].GetProperty("type").GetString() != "complete") throw new Exception("Missing completion");
    var report = events.First(x => x.GetProperty("type").GetString() == "report").GetProperty("report");
    if (!File.Exists(report.GetProperty("output_path").GetString())) throw new Exception("Missing model");
    if (!report.GetProperty("solid").GetProperty("printable").GetBoolean()) throw new Exception("Invalid solid");
    Console.WriteLine("PASS: C# client -> Python -> water-tight STL, progress, report, clean process exit.");

    using (var client = new EngineClient())
    {
        try { await client.RunAsync("", request, _ => { }, CancellationToken.None); throw new Exception("Expected collision error"); }
        catch (InvalidOperationException ex) when (ex.Message.Contains("输出已存在"))
        { Console.WriteLine("PASS: backend errors propagate to the C# caller."); }
    }
    using (var client = new EngineClient())
    using (var cancelled = new CancellationTokenSource())
    {
        cancelled.Cancel();
        var cancelledEvents = new List<JsonElement>();
        await client.RunAsync("", new { files = new[] { source }, output_dir = output + "-cancel", request.options }, cancelledEvents.Add, cancelled.Token);
        if (cancelledEvents[^1].GetProperty("type").GetString() != "cancelled") throw new Exception("Missing cancellation");
        Console.WriteLine("PASS: C# cancellation reaches the engine and stops cleanly.");
    }
}
finally
{
    // The only recursive targets are test-owned random directories created above.
    foreach (var path in new[] { output, output + "-cancel" })
        if (Directory.Exists(path)) Directory.Delete(path, recursive: true);
}
