using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Numerics;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
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
    private Vector3? indicatorTarget;
    private readonly Windows.UI.ViewManagement.UISettings uiSettings = new();
    private readonly Vector3Transition indicatorTransition = new() { Duration = TimeSpan.FromMilliseconds(180) };

    public MainWindow(IEnumerable<string>? initialFiles = null)
    {
        InitializeComponent();
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1220, 900));
        output.Text = settings.OutputDirectory;
        python.Text = settings.Python;
        if (Enum.TryParse<ElementTheme>(settings.Theme, out var theme)) Root.RequestedTheme = theme;
        pages.Add(BuildProject());
        pages.Add(BuildAdvanced());
        pages.Add(BuildActivity());
        pages.Add(BuildSettings());
        foreach (var page in pages) { page.Visibility = Visibility.Collapsed; PageHost.Children.Add(page); }
        Navigation.LayoutUpdated += (_, _) => UpdateNavigationIndicator(animate: false);
        Navigation.SelectedItem = Navigation.MenuItems[0];
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

    private static StackPanel Stack(params UIElement[] children)
    {
        var panel = new StackPanel { Spacing = 14 };
        foreach (var child in children) panel.Children.Add(child);
        return panel;
    }
    private static TextBlock Text(string value, double size = 14) => new() { Text = value, FontSize = size, TextWrapping = TextWrapping.Wrap };
    private ContentControl Card(string title, string description, params UIElement[] children)
    {
        var panel = Stack(Text(title, 20), Text(description));
        foreach (var child in children) panel.Children.Add(child);
        return new ContentControl { HorizontalContentAlignment = HorizontalAlignment.Stretch,
            Content = new Border { Style = (Style)Root.Resources["CardStyle"], Child = panel } };
    }
    private static ScrollViewer Scroll(UIElement content) => new()
    {
        Content = content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
        HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled, Padding = new Thickness(0, 0, 12, 6),
    };
    private static Button Button(string label, RoutedEventHandler action)
    {
        var button = new Button { Content = label };
        button.Click += action;
        return button;
    }
    private static StackPanel Row(params UIElement[] children)
    {
        var panel = Stack(children);
        panel.Orientation = Orientation.Horizontal;
        panel.Spacing = 8;
        return panel;
    }
    private static Grid Pair(FrameworkElement first, FrameworkElement second)
    {
        var grid = new Grid { ColumnSpacing = 12 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.Children.Add(first);
        Grid.SetColumn(second, 1); grid.Children.Add(second);
        return grid;
    }

    private Control BuildProject()
    {
        fileList.ItemsSource = files;
        fileList.AllowDrop = true;
        fileList.DragOver += (_, e) =>
        {
            e.AcceptedOperation = !busy && e.DataView.Contains(StandardDataFormats.StorageItems)
                ? DataPackageOperation.Copy : DataPackageOperation.None;
        };
        fileList.Drop += async (_, e) =>
        {
            if (busy || !e.DataView.Contains(StandardDataFormats.StorageItems)) return;
            try { AddFiles((await e.DataView.GetStorageItemsAsync()).OfType<StorageFile>().Select(f => f.Path)); }
            catch (Exception ex) { ShowError(ex); }
        };
        return Scroll(Stack(
            Card("把 Minecraft 投影带到现实", "打印封闭实体，或导出带原版贴图的 Blender 模型。内置 Minecraft 26.2 资源，无需安装游戏。"),
            Card("01  投影文件", "选择或拖入 .litematic 文件，支持批量转换。", fileList,
                Row(Button("添加文件", ChooseFiles), Button("移除所选", (_, _) =>
                { foreach (var path in fileList.SelectedItems.Cast<string>().ToArray()) files.Remove(path); }),
                Button("清空", (_, _) => files.Clear()))),
            Card("02  输出位置", "每个投影保存到独立的同名子文件夹；已有结果不会覆盖。",
                Pair(output, Button("浏览…", ChooseOutput))),
            Card("03  快速预设", "选择用途，再到高级参数调整细节。",
                Row(Button("3D 打印 · STL", (_, _) => ApplyPreset("print")),
                    Button("视觉 · OBJ", (_, _) => ApplyPreset("visual")),
                    Button("渲染 · 精确灯光", (_, _) => ApplyPreset("render"))),
                presetLabel, summary)));
    }

    private ComboBox Choice(string key, string header, params (string Label, string Value)[] values)
    {
        var combo = new ComboBox { Header = header, HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var (label, value) in values) combo.Items.Add(new ComboBoxItem { Content = label, Tag = value });
        combo.SelectedIndex = 0;
        choices[key] = combo;
        combo.SelectionChanged += (_, _) => Changed();
        return combo;
    }
    private NumberBox Number(string key, string header, double value, double minimum, double maximum)
    {
        var number = new NumberBox { Header = header, Value = value, Minimum = minimum, Maximum = maximum,
            SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Compact, SmallChange = 0.1 };
        numbers[key] = number;
        number.ValueChanged += (_, _) => Changed();
        return number;
    }
    private CheckBox Check(string key, string label)
    {
        var check = new CheckBox { Content = label };
        checks[key] = check;
        check.Checked += (_, _) => Changed(); check.Unchecked += (_, _) => Changed();
        return check;
    }
    private Control BuildAdvanced()
    {
        updating = true;
        var basic = Card("输出与几何", "STL 固定使用打印用途；视觉 OBJ 固定携带原版贴图。",
            Choice("output_format", "输出格式", ("STL", "stl"), ("OBJ", "obj")),
            Choice("geometry", "用途", ("打印 · 封闭实体", "print"), ("视觉 · 原版贴图", "visual")),
            Choice("water", "水体处理", ("完整方块", "cube"), ("忽略水体", "drop"), ("水位高度", "level")),
            Choice("fallback", "未知方块", ("回落成立方体", "cube"), ("忽略", "ignore")),
            Choice("optimize", "面数优化", ("安全优化", "safe"), ("原始网格", "raw"), ("实验性优化", "experimental")),
            Number("scale", "模型比例", 1, 0.0001, 10000),
            Check("center", "模型居中"), Check("stl_binary", "二进制 STL（取消勾选为 ASCII）"));
        printGroup = Card("实体与拓扑", "仅影响打印流程。最小厚度以方块为单位。",
            Number("minimum_thickness", "最小实体厚度", 1.0 / 16, 1.0 / 256, 1),
            Choice("components", "独立壳体", ("全部保留", "keep"), ("删除较小壳体", "remove-small"), ("仅保留主要壳体", "main")),
            Number("min_component_volume", "最小壳体体积", 1.0 / 4096, 0, 1e9),
            Choice("cavities", "封闭空腔", ("保留空腔", "preserve"), ("填充空腔", "fill")),
            Choice("boolean_fallback", "并集失败策略", ("局部体素 32 回退", "voxel32"), ("失败并停止", "fail")));
        visualGroup = Card("贴图与发光", "视觉模型适合渲染，可能存在开放边，不保证可直接打印。",
            Check("color", "OBJ 基础颜色"), Check("seamless_glass", "半透明无缝玻璃"),
            Choice("blender_lights", "Blender 发光", ("不发光", "none"), ("仅材质", "material"), ("精确灯光", "exact"), ("聚类灯光", "clustered")),
            Number("emission_strength", "发光强度倍率", 1, 0, 1000),
            Pair(emissionConfig, Button("选择 JSON", ChooseEmission)));
        regions.TextChanged += (_, _) => Changed();
        emissionConfig.TextChanged += (_, _) => Changed();
        updating = false;
        return Scroll(Stack(basic, printGroup, visualGroup,
            Card("区域选择", "单文件可读取可用区域；批量转换默认使用所有区域。", regions,
                Button("读取所选投影区域", ReadRegions))));
    }

    private Control BuildActivity()
    {
        return Scroll(Stack(Row(Button("打开输出文件夹", OpenOutput),
                Button("保存报告…", SaveReport), Button("清空日志", (_, _) => log.Text = "")),
            Card("实时日志", "显示转换阶段、处理进度与错误。", log),
            Card("转换报告", "包含批次内所有已完成投影的统计数据。报告也会自动保存到模型旁。", reportText)));
    }
    private Control BuildSettings()
    {
        var theme = new ComboBox { Header = "外观", HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var name in new[] { "跟随系统", "浅色", "深色" }) theme.Items.Add(name);
        theme.SelectedIndex = (int)Root.RequestedTheme;
        theme.SelectionChanged += (_, _) =>
        {
            Root.RequestedTheme = (ElementTheme)theme.SelectedIndex;
            settings.Theme = Root.RequestedTheme.ToString();
            SaveSettings();
        };
        return Scroll(Stack(Card("应用设置", "设置保存在当前用户的本地应用数据目录。", theme, python,
            Button("保存设置", (_, _) => { SaveSettings(); ShowNotice("已保存", "应用设置已更新。", InfoBarSeverity.Success); })),
            Card("关于 Litematica 3D", "原生 WinUI 3 界面 · Python 转换引擎 · Minecraft 26.2 内置资源",
                Text("首次使用请运行仓库根目录的 setup_winui.ps1，再运行 run_winui.ps1。解释器留空时自动查找仓库 .venv。"))));
    }
    private void SaveSettings()
    {
        try { settings.OutputDirectory = output.Text.Trim(); settings.Python = python.Text.Trim(); settings.Save(); }
        catch (Exception ex) { ShowError(ex); }
    }
    private void Navigate(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is not NavigationViewItem item || !int.TryParse(item.Tag?.ToString(), out var index) || pages.Count <= index) return;
        UpdateNavigationIndicator(animate: true);
        var revision = ++navigationRevision;
        // Let WinUI submit the compositor animation before measuring the new page.
        // Rapid selections coalesce: a queued, obsolete page must never appear.
        DispatcherQueue.TryEnqueue(DispatcherQueuePriority.Low, () =>
        {
            if (revision != navigationRevision || visiblePage == index) return;
            if (visiblePage >= 0) pages[visiblePage].Visibility = Visibility.Collapsed;
            pages[index].Visibility = Visibility.Visible;
            visiblePage = index;
            PageTitle.Text = item.Content.ToString();
        });
    }

    private void UpdateNavigationIndicator(bool animate)
    {
        if (Navigation.SelectedItem is not NavigationViewItem item || !item.IsLoaded || item.ActualHeight <= 0) return;
        var position = item.TransformToVisual(Root).TransformPoint(new Windows.Foundation.Point(4, (item.ActualHeight - 16) / 2));
        var target = new Vector3((float)position.X, (float)position.Y, 0);
        // LayoutUpdated must not restart or snap an in-flight selection animation.
        if (indicatorTarget is { } previous && Vector3.DistanceSquared(previous, target) < 0.01f) return;
        NavigationIndicator.TranslationTransition = animate && indicatorTarget.HasValue && uiSettings.AnimationsEnabled
            ? indicatorTransition : null;
        // TranslationTransition runs on the compositor and retargets from its
        // current presentation position, including when clicks interrupt it.
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
        presetLabel.Text = preset switch { "print" => "当前预设 · 3D 打印", "visual" => "当前预设 · 视觉", _ => "当前预设 · 渲染" };
    }
    private void Changed()
    {
        if (updating) return;
        Sync(); presetLabel.Text = "当前预设 · 自定义";
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
        numbers["min_component_volume"].IsEnabled = Value("components") == "remove-small";
        var emission = visual && Value("blender_lights") != "none";
        numbers["emission_strength"].IsEnabled = emission; emissionConfig.IsEnabled = emission;
        summary.Text = $"{Value("output_format").ToUpperInvariant()} · {Value("geometry")} · 水体 {Value("water")} · 优化 {Value("optimize")}\n" +
            $"比例 {numbers["scale"].Value:g} · 壳体 {Value("components")} · 空腔 {Value("cavities")} · 发光 {(visual ? Value("blender_lights") : "none")}";
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
            SaveSettings(); Notice.IsOpen = false; reports.Clear(); reportText.Text = ""; Progress.Value = 0;
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
                Status.Text = text; AppendLog(text); break;
            case "log": AppendLog(text); break;
            case "report":
                reports.Add(item.GetProperty("report").Clone());
                reportText.Text = JsonSerializer.Serialize(reports, new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
                AppendLog($"模型已保存：{reports[^1].GetProperty("output_path").GetString()}"); break;
            case "complete":
                Progress.Value = 100; Status.Text = text; AppendLog(text);
                ShowNotice("转换完成", text, InfoBarSeverity.Success); Navigation.SelectedItem = Navigation.MenuItems[2]; break;
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
        busy = value; StartButton.IsEnabled = !value; CancelButton.IsEnabled = value;
        pages[0].IsEnabled = !value; pages[1].IsEnabled = !value; pages[3].IsEnabled = !value;
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
