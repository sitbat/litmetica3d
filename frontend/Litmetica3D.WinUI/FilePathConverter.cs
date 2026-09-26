using Microsoft.UI.Xaml.Data;
namespace Litmetica3D.WinUI;

public sealed class FilePathConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
        => parameter as string == "directory" ? Path.GetDirectoryName(value?.ToString() ?? "") ?? ""
                                              : Path.GetFileName(value?.ToString() ?? "");
    public object ConvertBack(object value, Type targetType, object parameter, string language)
        => throw new NotSupportedException();
}
