#if DEBUG
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Graphics.Imaging;
using Windows.Storage;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Text.Json;

namespace Litmetica3D.WinUI;

// Runs in the real WinUI dispatcher. No global input, screenshots, or user files.
public sealed partial class MainWindow
{
    internal async Task RunLayoutSmokeAsync(string folder)
    {
        Directory.CreateDirectory(folder);
        var checksRun = new List<string>();
        void Check(bool condition, string name)
        {
            if (!condition) throw new InvalidOperationException(name);
            checksRun.Add(name);
        }
        async Task Capture(string name)
        {
            await Task.Delay(280);
            Root.UpdateLayout();
            var bitmap = new RenderTargetBitmap();
            await bitmap.RenderAsync(Root);
            var pixels = await bitmap.GetPixelsAsync();
            var target = await StorageFolder.GetFolderFromPathAsync(folder);
            var file = await target.CreateFileAsync(name + ".png", CreationCollisionOption.ReplaceExisting);
            using var stream = await file.OpenAsync(FileAccessMode.ReadWrite);
            var encoder = await BitmapEncoder.CreateAsync(BitmapEncoder.PngEncoderId, stream);
            encoder.SetPixelData(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Premultiplied,
                (uint)bitmap.PixelWidth, (uint)bitmap.PixelHeight, 96, 96, pixels.ToArray());
            await encoder.FlushAsync();
            checksRun.Add($"{name}: {Root.ActualWidth} x {Root.ActualHeight}, workspace {workspace.ActualWidth}");
        }
        try
        {
            await Task.Delay(500);
            Root.RequestedTheme = ElementTheme.Light;
            Check(!StartButton.IsEnabled && !advancedOptions.IsExpanded, "Empty state is safe and advanced options are collapsed");
            Check(Value("geometry") == "print" && presetButtons["print"].IsChecked == true, "Default print preset selected");
            await Capture("01-workspace-light");

            presetButtons["visual"].IsChecked = true;
            Check(Value("output_format") == "obj" && Value("geometry") == "visual", "Visual radio changes actual conversion parameters");
            Check(visualGroup.Visibility == Visibility.Visible && printGroup.Visibility == Visibility.Collapsed, "Relevant parameter groups shown");
            presetButtons["render"].IsChecked = true;
            Check(Value("blender_lights") == "exact" && checks["seamless_glass"].IsChecked == true, "Render preset includes exact lights and seamless glass");
            numbers["scale"].Value = 2;
            Check(presetButtons.Values.All(x => x.IsChecked == false), "Editing a parameter shows custom configuration");
            Set("output_format", "stl");
            Check(Value("geometry") == "print" && !choices["geometry"].IsEnabled, "STL remains constrained to print mode");
            ApplyPreset("print");
            AddFiles([Path.Combine(folder, "中文 测试.litematic"), Path.Combine(folder, "第二个投影.litematic")]);
            output.Text = folder;
            Check(StartButton.IsEnabled && fileList.Visibility == Visibility.Visible && emptyFiles.Visibility == Visibility.Collapsed, "Adding files updates queue and primary action");
            Check((string)StartButton.Content == "转换 2 个投影", "Batch action shows queue count");
            SetBusy(true);
            Check(!StartButton.IsEnabled && !pages[0].IsEnabled && !pages[2].IsEnabled && pages[1].IsEnabled && CancelButton.IsEnabled, "Busy state locks editing while activity remains available");
            SetBusy(false);
            await Capture("02-workspace-files");
            fileList.SelectedItems.Add(files[0]);
            Check(fileList.SelectedItems.Count == 1, "Queue supports selecting items for removal");
            files.Remove(files[0]);
            Check(files.Count == 1 && (string)StartButton.Content == "开始转换", "Removing a file updates batch action");

            Root.RequestedTheme = ElementTheme.Dark;
            ApplyPreset("visual");
            await Capture("03-workspace-dark");
            advancedOptions.IsExpanded = true;
            await Task.Delay(280);
            advancedOptions.StartBringIntoView(new BringIntoViewOptions { AnimationDesired = false, VerticalAlignmentRatio = 0 });
            await Capture("04-advanced");
            NavigateTo(1); NavigateTo(2); NavigateTo(0);
            await Task.Delay(200);
            Check(visiblePage == 0 && pages[0].Visibility == Visibility.Visible && pages[1].Visibility == Visibility.Collapsed, "Rapid navigation shows only the latest selected page");
            advancedOptions.IsExpanded = false;
            ((ScrollViewer)pages[0]).ChangeView(null, 0, null, true);
            Root.RequestedTheme = ElementTheme.Light;
            AppWindow.Resize(new Windows.Graphics.SizeInt32(850, 940));
            await Capture("05-workspace-narrow");
            Check(workspace.ColumnDefinitions[1].Width.Value == 0, "Narrow windows stack the use-case panel");
            AppWindow.Resize(new Windows.Graphics.SizeInt32(1380, 1060));
            await Task.Delay(250);
            using (var report = JsonDocument.Parse("{\"output_path\":\"C:/models/demo/demo.stl\",\"triangles\":12,\"rendered_blocks\":1,\"geometry_mode\":\"print\"}"))
                reports.Add(report.RootElement.Clone());
            UpdateResults();
            Check(resultCards.Children.Count == 1 && emptyResults.Visibility == Visibility.Collapsed, "Completed report renders a result card");
            NavigateTo(1);
            await Capture("06-activity");
            AppWindow.Resize(new Windows.Graphics.SizeInt32(1180, 900));
            NavigateTo(2);
            await Capture("07-settings");
            Root.RequestedTheme = ElementTheme.Dark;
            await Capture("08-settings-dark");
            await File.WriteAllTextAsync(Path.Combine(folder, "checks.txt"), string.Join(Environment.NewLine, checksRun));
            Environment.Exit(0);
        }
        catch (Exception ex)
        {
            await File.WriteAllTextAsync(Path.Combine(folder, "failure.txt"), ex.ToString());
            Environment.Exit(1);
        }
    }
}
#endif
