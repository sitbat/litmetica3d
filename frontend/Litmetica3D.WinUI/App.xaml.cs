using Microsoft.UI.Xaml;

namespace Litmetica3D.WinUI;

public partial class App : Application
{
    private Window? window;
    public App() => InitializeComponent();
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
#if DEBUG
        var arguments = Environment.GetCommandLineArgs();
        if (arguments.Length == 3 && arguments[1] == "--layout-smoke")
        {
            var testWindow = new MainWindow();
            window = testWindow;
            window.Activate();
            _ = testWindow.RunLayoutSmokeAsync(Path.GetFullPath(arguments[2]));
            return;
        }
#endif
        window = new MainWindow(Environment.GetCommandLineArgs().Skip(1));
        window.Activate();
    }
}
