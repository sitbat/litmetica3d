using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Numerics;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Media.Animation;
using Microsoft.UI.Dispatching;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;
using Windows.Storage.Pickers;

namespace Litmetica3D.WinUI;

public sealed partial class MainWindow : Window
{
    private readonly ObservableCollection<string> files = [];
    private readonly Dictionary<string, ComboBox> choices = [];
    private readonly Dictionary<string, NumberBox> numbers = [];
    private readonly Dictionary<string, CheckBox> checks = [];
    private readonly List<Control> pages = [];
    private readonly List<JsonElement> reports = [];
    private readonly UserSettings settings = UserSettings.Load();
    private readonly TextBox output = new() { PlaceholderText = "选择输出文件夹", HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly TextBox regions = new() { Header = "区域筛选", PlaceholderText = "留空转换全部；多个区域用英文逗号分隔（仅单文件）" };
    private readonly TextBox emissionConfig = new() { Header = "自定义发光规则", PlaceholderText = "可选 .json 文件" };
    private readonly TextBox python = new() { Header = "Python 解释器", PlaceholderText = "自动使用仓库 .venv；也可填写 python.exe 的完整路径" };
    private readonly TextBlock presetLabel = new() { FontSize = 18, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly TextBlock summary = new() { TextWrapping = TextWrapping.Wrap, IsTextSelectionEnabled = true, Opacity = 0.75 };
    private readonly TextBox log = new() { AcceptsReturn = true, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, MinHeight = 200 };
    private readonly TextBox reportText = new() { AcceptsReturn = true, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, MinHeight = 200 };
    private readonly ListView fileList = new() { SelectionMode = ListViewSelectionMode.Multiple, MinHeight = 110, MaxHeight = 210 };
    private readonly DispatcherTimer timer = new() { Interval = TimeSpan.FromSeconds(1) };
    private readonly Stopwatch watch = new();
    private Control visualGroup = null!;
    private Control printGroup = null!;
    private CancellationTokenSource? cancellation;
    private EngineClient? engine;
    private bool updating;
    private bool busy;
    private int navigationRevision;
    private int visiblePage = -1;
    private int selectedPage;
    private Vector3? indicatorTarget;
    private readonly Windows.UI.ViewManagement.UISettings uiSettings = new();
    private readonly Vector3Transition indicatorTransition = new() { Duration = TimeSpan.FromMilliseconds(180) };

    public MainWindow(IEnumerable<string>? initialFiles = null)
    {
        InitializeComponent();
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1180, 900));
        output.Text = settings.OutputDirectory;
        python.Text = settings.Python;
        if (Enum.TryParse<ElementTheme>(settings.Theme, out var theme)) Root.RequestedTheme = theme;
        var advanced = BuildAdvanced();
        pages.Add(BuildProject(advanced));
        pages.Add(BuildActivity());
        pages.Add(BuildSettings());
        foreach (var page in pages) { page.Visibility = Visibility.Collapsed; PageHost.Children.Add(page); }
        Header.LayoutUpdated += (_, _) => UpdateNavigationIndicator(animate: false);
        files.CollectionChanged += (_, _) =>
        {
            UpdateFileState();
            if (!busy) Status.Text = files.Count == 0 ? "添加投影，开始创作" : $"已就绪 · {files.Count} 个投影";
        };
        output.TextChanged += (_, _) => UpdateFileState();
        NavigateTo(0);
        ApplyPreset("print");
        if (initialFiles != null) AddFiles(initialFiles.Where(File.Exists));
        timer.Tick += (_, _) => Elapsed.Text = $"总耗时 {watch.Elapsed:hh\\:mm\\:ss}";
        Closed += (_, _) => { cancellation?.Cancel(); engine?.Dispose(); timer.Stop(); };
        AppWindow.Closing += (_, args) =>
        {
            if (!busy) return;
            args.Cancel = true;
            ShowNotice("转换正在进行", "请先取消转换，完成后再关闭窗口。", InfoBarSeverity.Informational);
        };
    }

    private void SaveSettings()
    {
        try { settings.OutputDirectory = output.Text.Trim(); settings.Python = python.Text.Trim(); settings.Save(); }
        catch (Exception ex) { ShowError(ex); }
    }
    private void Navigate(object sender, RoutedEventArgs args)
    {
        if (sender is ToggleButton button && int.TryParse(button.Tag?.ToString(), out var index)) NavigateTo(index);
    }
    private void NavigateTo(int index)
    {
        if (index < 0 || index >= pages.Count) return;
        selectedPage = index;
        var tabs = new[] { ConvertTab, ActivityTab, SettingsTab };
        for (var i = 0; i < tabs.Length; i++) tabs[i].IsChecked = i == index;
        UpdateNavigationIndicator(animate: true);
        var revision = ++navigationRevision;
        DispatcherQueue.TryEnqueue(DispatcherQueuePriority.Low, () =>
        {
            if (revision != navigationRevision || visiblePage == index) return;
            if (visiblePage >= 0) pages[visiblePage].Visibility = Visibility.Collapsed;
            pages[index].Visibility = Visibility.Visible;
            visiblePage = index;
        });
    }

    private void UpdateNavigationIndicator(bool animate)
    {
        var item = new[] { ConvertTab, ActivityTab, SettingsTab }[selectedPage];
        if (!item.IsLoaded || item.ActualHeight <= 0) return;
        var position = item.TransformToVisual(Root).TransformPoint(
            new Windows.Foundation.Point((item.ActualWidth - 24) / 2, item.ActualHeight + 5));
        var target = new Vector3((float)position.X, (float)position.Y, 0);
        if (indicatorTarget is { } previous && Vector3.DistanceSquared(previous, target) < 0.01f) return;
        NavigationIndicator.TranslationTransition = animate && indicatorTarget.HasValue && uiSettings.AnimationsEnabled
            ? indicatorTransition : null;
        NavigationIndicator.Translation = target;
        indicatorTarget = target;
        NavigationIndicator.Opacity = 1;
    }
    private string Value(string key) => ((ComboBoxItem)choices[key].SelectedItem).Tag.ToString()!;
    private void Set(string key, string value) => choices[key].SelectedItem = choices[key].Items.Cast<ComboBoxItem>().First(i => (string)i.Tag == value);
    private void ApplyPreset(string preset)
    {
        if (busy) return;
        updating = true;
        var print = preset == "print";
        Set("output_format", print ? "stl" : "obj"); Set("geometry", print ? "print" : "visual");
        Set("water", preset == "visual" ? "level" : "drop"); Set("fallback", "ignore"); Set("optimize", "safe");
        Set("components", print ? "main" : "keep"); Set("cavities", print ? "fill" : "preserve");
        Set("boolean_fallback", "voxel32"); Set("blender_lights", preset == "visual" ? "material" : "exact");
        numbers["scale"].Value = 1; numbers["minimum_thickness"].Value = 1.0 / 16;
        numbers["min_component_volume"].Value = 1.0 / 4096; numbers["emission_strength"].Value = 1;
        foreach (var check in checks.Values) check.IsChecked = false;
        checks["stl_binary"].IsChecked = true; checks["seamless_glass"].IsChecked = preset == "render";
        regions.Text = ""; emissionConfig.Text = "";
        updating = false;
        Sync();
        SelectPreset(preset);
    }
    private void Changed()
    {
        if (updating) return;
        Sync(); SelectPreset(null);
    }
    private void Sync()
    {
        updating = true;
        var stl = Value("output_format") == "stl";
        if (stl) Set("geometry", "print");
        choices["geometry"].IsEnabled = !stl;
        checks["stl_binary"].IsEnabled = stl;
        var visual = Value("geometry") == "visual";
        visualGroup.IsEnabled = visual; printGroup.IsEnabled = !visual;
        visualGroup.Visibility = visual ? Visibility.Visible : Visibility.Collapsed;
        printGroup.Visibility = visual ? Visibility.Collapsed : Visibility.Visible;
        numbers["min_component_volume"].IsEnabled = Value("components") == "remove-small";
        var emission = visual && Value("blender_lights") != "none";
        numbers["emission_strength"].IsEnabled = emission; emissionConfig.IsEnabled = emission;
        string Label(string key) => ((ComboBoxItem)choices[key].SelectedItem).Content.ToString() ?? "";
        summary.Text = $"{Value("output_format").ToUpperInvariant()} · {(visual ? "原版贴图" : "封闭实体")}\n" +
            $"{Label("optimize")} · 比例 × {numbers["scale"].Value:g}\n" +
            (visual ? $"灯光：{Label("blender_lights")}" : $"壳体：{Label("components")}");
        updating = false;
    }

    private void InitializePicker(object picker) => WinRT.Interop.InitializeWithWindow.Initialize(picker, WinRT.Interop.WindowNative.GetWindowHandle(this));
    private async Task<IReadOnlyList<StorageFile>> PickFiles(string extension, bool multiple)
    {
        var picker = new FileOpenPicker(); InitializePicker(picker); picker.FileTypeFilter.Add(extension);
        if (multiple) return await picker.PickMultipleFilesAsync();
        var file = await picker.PickSingleFileAsync();
        return file == null ? [] : [file];
    }
    private async void ChooseFiles(object sender, RoutedEventArgs args)
    {
        try { AddFiles((await PickFiles(".litematic", true)).Select(f => f.Path)); } catch (Exception ex) { ShowError(ex); }
    }
    private void AddFiles(IEnumerable<string> paths)
    {
        if (busy) return;
        foreach (var path in paths)
        {
            if (!path.EndsWith(".litematic", StringComparison.OrdinalIgnoreCase)) continue;
            var absolute = Path.GetFullPath(path);
            if (!files.Contains(absolute, StringComparer.OrdinalIgnoreCase)) files.Add(absolute);
        }
        if (files.Count > 0 && string.IsNullOrWhiteSpace(output.Text)) output.Text = Path.Combine(Path.GetDirectoryName(files[0])!, "3D-output");
        UpdateFileState();
    }
    private async void ChooseOutput(object sender, RoutedEventArgs args)
    {
        try
        {
            var picker = new FolderPicker(); InitializePicker(picker); picker.FileTypeFilter.Add("*");
            var folder = await picker.PickSingleFolderAsync();
            if (folder != null) { output.Text = folder.Path; SaveSettings(); }
        }
        catch (Exception ex) { ShowError(ex); }
    }
    private async void ChooseEmission(object sender, RoutedEventArgs args)
    {
        try { var picked = await PickFiles(".json", false); if (picked.Count > 0) emissionConfig.Text = picked[0].Path; }
        catch (Exception ex) { ShowError(ex); }
    }
    private async void ReadRegions(object sender, RoutedEventArgs args)
    {
        if (files.Count != 1) { ShowNotice("请选择一个投影", "区域读取与筛选仅适用于单文件。", InfoBarSeverity.Warning); return; }
        var button = (Button)sender; button.IsEnabled = false;
        try
        {
            var root = EngineClient.FindRoot();
            var executable = python.Text.Trim();
            if (executable.Length == 0) executable = Path.Combine(root, ".venv", "Scripts", "python.exe");
            var start = new ProcessStartInfo(executable) { WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true, StandardOutputEncoding = System.Text.Encoding.UTF8, StandardErrorEncoding = System.Text.Encoding.UTF8 };
            start.Environment["PYTHONUTF8"] = "1";
            foreach (var arg in new[] { "-m", "litmetica3d", files[0], "--list-regions" }) start.ArgumentList.Add(arg);
            using var process = Process.Start(start)!;
            var result = process.StandardOutput.ReadToEndAsync(); var error = process.StandardError.ReadToEndAsync();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
            try { await process.WaitForExitAsync(timeout.Token); }
            catch (OperationCanceledException) { process.Kill(true); throw new TimeoutException("读取区域超时，请手动填写区域名称。"); }
            var text = await result; var diagnostic = await error;
            if (process.ExitCode != 0) throw new InvalidOperationException(diagnostic);
            regions.Text = string.Join(", ", text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries));
            ShowNotice("区域已读取", regions.Text, InfoBarSeverity.Success);
        }
        catch (Exception ex) { ShowError(ex); }
        finally { button.IsEnabled = true; }
    }
    private Dictionary<string, object> Snapshot()
    {
        var options = new Dictionary<string, object>();
        foreach (var key in choices.Keys) options[key] = Value(key);
        foreach (var (key, number) in numbers)
        {
            if (!double.IsFinite(number.Value)) throw new ArgumentException($"请填写有效的数值：{number.Header}");
            options[key] = number.Value;
        }
        foreach (var (key, check) in checks) options[key] = check.IsChecked == true;
        var visual = Value("geometry") == "visual";
        options["textures"] = visual; options["emission"] = visual && Value("blender_lights") != "none";
        options["emission_config"] = (bool)options["emission"] ? emissionConfig.Text.Trim() : "";
        options["regions"] = regions.Text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return options;
    }
    private async void Start(object sender, RoutedEventArgs args)
    {
        if (busy) return;
        try
        {
            if (files.Count == 0) throw new ArgumentException("请先添加 .litematic 投影文件。");
            if (string.IsNullOrWhiteSpace(output.Text)) throw new ArgumentException("请选择输出文件夹。");
            var request = new { files = files.ToArray(), output_dir = Path.GetFullPath(output.Text.Trim()), options = Snapshot() };
            SaveSettings(); Notice.IsOpen = false; reports.Clear(); reportText.Text = ""; UpdateResults(); Progress.Value = 0; ProgressLabel.Text = "";
            SetBusy(true); watch.Restart(); timer.Start(); Status.Text = "正在启动转换引擎…"; AppendLog("开始转换");
            cancellation = new(); engine = new();
            await engine.RunAsync(python.Text.Trim(), request, HandleEvent, cancellation.Token);
        }
        catch (OperationCanceledException)
        {
            Status.Text = "转换已取消";
            AppendLog("转换进程已停止。已完成的模型保留；输出目录中可能残留 .litmetica3d- 临时文件夹。");
        }
        catch (Exception ex) { Status.Text = "转换失败"; AppendLog(ex.Message); ShowError(ex); }
        finally
        {
            timer.Stop(); watch.Stop(); Elapsed.Text = $"总耗时 {watch.Elapsed:hh\\:mm\\:ss}";
            engine?.Dispose(); engine = null; cancellation?.Dispose(); cancellation = null; SetBusy(false);
        }
    }
    private void HandleEvent(JsonElement item)
    {
        // Async pipe reads resume on the UI context; background safety is explicit.
        if (!DispatcherQueue.HasThreadAccess) { DispatcherQueue.TryEnqueue(() => HandleEvent(item)); return; }
        var kind = item.GetProperty("type").GetString();
        var text = item.TryGetProperty("text", out var message) ? message.GetString() ?? "" : "";
        switch (kind)
        {
            case "progress":
                Progress.Value = Math.Clamp(item.GetProperty("value").GetDouble() * 100, 0, 100);
                Status.Text = text; ProgressLabel.Text = $"{Progress.Value:0}%"; AppendLog(text); break;
            case "log": AppendLog(text); break;
            case "report":
                reports.Add(item.GetProperty("report").Clone());
                reportText.Text = JsonSerializer.Serialize(reports, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
                UpdateResults(); AppendLog($"模型已保存：{reports[^1].GetProperty("output_path").GetString()}"); break;
            case "complete":
                Progress.Value = 100; Status.Text = text; AppendLog(text);
                ProgressLabel.Text = "100%"; ShowNotice("转换完成", text, InfoBarSeverity.Success); NavigateTo(1); break;
            case "cancelled": Status.Text = text; AppendLog(text); break;
            case "error": AppendLog(text); break;
        }
    }
    private void Cancel(object sender, RoutedEventArgs args)
    {
        cancellation?.Cancel(); CancelButton.IsEnabled = false; Status.Text = "正在取消转换…";
    }
    private void SetBusy(bool value)
    {
        busy = value; CancelButton.IsEnabled = value;
        CancelButton.Visibility = value ? Visibility.Visible : Visibility.Collapsed;
        Progress.Visibility = value || Progress.Value > 0 ? Visibility.Visible : Visibility.Collapsed;
        pages[0].IsEnabled = !value; pages[2].IsEnabled = !value;
        UpdateFileState();
    }
    private void AppendLog(string message)
    {
        if (log.Text.Length > 60000) log.Text = log.Text[^40000..];
        log.Text += $"[{DateTime.Now:HH:mm:ss}] {message}\n";
    }
    private async void OpenOutput(object sender, RoutedEventArgs args)
    {
        try
        {
            if (!Directory.Exists(output.Text.Trim())) throw new DirectoryNotFoundException("输出文件夹尚不存在。");
            await Windows.System.Launcher.LaunchFolderAsync(await StorageFolder.GetFolderFromPathAsync(Path.GetFullPath(output.Text.Trim())));
        }
        catch (Exception ex) { ShowError(ex); }
    }
    private async void SaveReport(object sender, RoutedEventArgs args)
    {
        try
        {
            if (reports.Count == 0) throw new InvalidOperationException("当前还没有已完成的转换报告。");
            var picker = new FileSavePicker { SuggestedFileName = "litematica-reports" }; InitializePicker(picker);
            picker.FileTypeChoices.Add("JSON 报告", new List<string> { ".json" });
            var file = await picker.PickSaveFileAsync();
            if (file != null) await FileIO.WriteTextAsync(file, reportText.Text);
        }
        catch (Exception ex) { ShowError(ex); }
    }
    private void ShowError(Exception ex) => ShowNotice("操作未完成", ex.Message, InfoBarSeverity.Error);
    private void ShowNotice(string title, string message, InfoBarSeverity severity)
    {
        Notice.Title = title; Notice.Message = message; Notice.Severity = severity; Notice.IsOpen = true;
    }
}
