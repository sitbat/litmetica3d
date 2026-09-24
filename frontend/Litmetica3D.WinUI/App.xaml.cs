using Microsoft.UI.Xaml;

namespace Litmetica3D.WinUI;

public partial class App : Application
{
    private Window? window;
    public App() => InitializeComponent();
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        window = new MainWindow(Environment.GetCommandLineArgs().Skip(1));
        window.Activate();
    }
}
