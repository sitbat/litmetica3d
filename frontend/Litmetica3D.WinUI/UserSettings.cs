using System.Text.Json;

namespace Litmetica3D.WinUI;

public sealed class UserSettings
{
    public string OutputDirectory { get; set; } = "";
    public string Python { get; set; } = "";
    public string Theme { get; set; } = "Default";
    private static string FilePath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Litmetica3D", "winui-settings.json");
    public static UserSettings Load()
    {
        try { return JsonSerializer.Deserialize<UserSettings>(File.ReadAllText(FilePath)) ?? new(); }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException) { return new(); }
    }
    public void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllText(FilePath + ".tmp", JsonSerializer.Serialize(this));
        File.Move(FilePath + ".tmp", FilePath, overwrite: true);
    }
}
