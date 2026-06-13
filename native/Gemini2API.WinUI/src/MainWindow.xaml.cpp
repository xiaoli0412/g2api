#include "pch.h"
#include "MainWindow.xaml.h"
#include "Views/CookiesPage.xaml.h"
#include "Views/HomePage.xaml.h"
#include "Views/LogsPage.xaml.h"
#include "Views/ModelsPage.xaml.h"
#include "Views/PageContent.h"
#include "Views/ServerPage.xaml.h"
#include "Views/SettingsPage.xaml.h"
#include "Views/StreamingPage.xaml.h"
#include "NativeLog.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

#include <algorithm>
#include <chrono>
#include <iomanip>
#include <sstream>

using namespace winrt;
using namespace Windows::Data::Json;
using namespace Microsoft::UI::Xaml;
using namespace Microsoft::UI::Xaml::Automation;
using namespace Microsoft::UI::Xaml::Controls;
using namespace Microsoft::UI::Xaml::Media;

namespace
{
    constexpr double kNavWidth = 48.0;
    constexpr double kTitleBarHeight = 40.0;
    constexpr double kPagePaddingX = 20.0;
    constexpr double kPagePaddingY = 16.0;
    constexpr double kContentSpacing = 16.0;
    constexpr double kPanelPadding = 16.0;
    constexpr double kPanelSpacing = 8.0;
    constexpr double kCornerRadius = 4.0;
    constexpr double kTitleFontSize = 14.0;
    constexpr double kBodyFontSize = 13.0;
    constexpr double kSecondaryFontSize = 12.0;
    constexpr double kCaptionFontSize = 11.0;

    Microsoft::UI::Xaml::Media::SolidColorBrush ColorBrush(uint8_t a, uint8_t r, uint8_t g, uint8_t b)
    {
        return Microsoft::UI::Xaml::Media::SolidColorBrush(Windows::UI::Color{ a, r, g, b });
    }

    Brush ResourceBrush(wchar_t const* key)
    {
        std::wstring_view name{ key };
        if (name == L"AppSurfaceBrush") return ColorBrush(235, 32, 32, 32);
        if (name == L"AppLayerBrush") return ColorBrush(242, 37, 37, 37);
        if (name == L"AppControlBrush") return ColorBrush(255, 43, 43, 43);
        if (name == L"AppHoverBrush") return ColorBrush(255, 45, 45, 45);
        if (name == L"AppSelectedBrush") return ColorBrush(255, 59, 59, 59);
        if (name == L"AppBorderBrush") return ColorBrush(255, 51, 51, 51);
        if (name == L"AppAccentBrush") return ColorBrush(255, 0, 120, 212);
        if (name == L"AppDangerBrush") return ColorBrush(255, 232, 17, 35);
        if (name == L"AppTextBrush") return ColorBrush(255, 255, 255, 255);
        if (name == L"AppSecondaryTextBrush") return ColorBrush(255, 153, 153, 153);
        if (name == L"AppDisabledTextBrush") return ColorBrush(255, 102, 102, 102);
        return ColorBrush(255, 255, 255, 255);
    }

    std::wstring ReadEnvironmentValue(wchar_t const* name)
    {
        DWORD required = GetEnvironmentVariableW(name, nullptr, 0);
        if (required == 0)
        {
            return {};
        }

        std::wstring value(required, L'\0');
        DWORD written = GetEnvironmentVariableW(name, value.data(), required);
        if (written == 0)
        {
            return {};
        }

        value.resize(written);
        return value;
    }

    std::wstring ToImageUri(std::wstring value)
    {
        if (value.rfind(L"file://", 0) == 0 ||
            value.rfind(L"http://", 0) == 0 ||
            value.rfind(L"https://", 0) == 0)
        {
            return value;
        }

        for (auto& ch : value)
        {
            if (ch == L'\\')
            {
                ch = L'/';
            }
        }

        return L"file:///" + value;
    }

    std::wstring ExecutableDirectory()
    {
        wchar_t path[MAX_PATH]{};
        DWORD length = GetModuleFileNameW(nullptr, path, ARRAYSIZE(path));
        if (length == 0 || length >= ARRAYSIZE(path))
        {
            return {};
        }

        std::wstring value(path, length);
        auto slash = value.find_last_of(L"\\/");
        if (slash == std::wstring::npos)
        {
            return {};
        }
        return value.substr(0, slash);
    }

    std::wstring ParentDirectory(std::wstring const& value)
    {
        auto slash = value.find_last_of(L"\\/");
        if (slash == std::wstring::npos)
        {
            return {};
        }
        return value.substr(0, slash);
    }

    std::wstring PathJoin(std::wstring left, std::wstring const& right)
    {
        if (left.empty())
        {
            return right;
        }
        if (left.back() != L'\\' && left.back() != L'/')
        {
            left += L'\\';
        }
        return left + right;
    }

    bool FileExists(std::wstring const& path)
    {
        DWORD attributes = GetFileAttributesW(path.c_str());
        return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
    }

    bool DirectoryExists(std::wstring const& path)
    {
        DWORD attributes = GetFileAttributesW(path.c_str());
        return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    }

    std::wstring FindRepositoryRoot()
    {
        auto current = ExecutableDirectory();
        for (int i = 0; i < 8 && !current.empty(); ++i)
        {
            if (DirectoryExists(PathJoin(current, L"gemini_web2api")) &&
                FileExists(PathJoin(current, L"config.example.json")))
            {
                return current;
            }
            current = ParentDirectory(current);
        }
        return {};
    }

    std::wstring BackendConfigPath(std::wstring const& repoRoot)
    {
        auto config = PathJoin(repoRoot, L"config.json");
        if (FileExists(config))
        {
            return config;
        }
        return PathJoin(repoRoot, L"config.example.json");
    }

    std::wstring FindSupervisorExecutable(std::wstring const& repoRoot)
    {
        auto packaged = PathJoin(ExecutableDirectory(), L"gemini2api-supervisor.exe");
        if (FileExists(packaged))
        {
            return packaged;
        }

        if (!repoRoot.empty())
        {
            auto release = PathJoin(repoRoot, L"native\\supervisor-rs\\target\\release\\gemini2api-supervisor.exe");
            if (FileExists(release))
            {
                return release;
            }

            auto debug = PathJoin(repoRoot, L"native\\supervisor-rs\\target\\debug\\gemini2api-supervisor.exe");
            if (FileExists(debug))
            {
                return debug;
            }
        }

        return {};
    }

    bool TryConfigurePersonalVisualLayer(Image const& image)
    {
        auto imagePath = ReadEnvironmentValue(L"GEMINI2API_VISUAL_IMAGE");
        if (imagePath.empty())
        {
            return false;
        }

        try
        {
            Microsoft::UI::Xaml::Media::Imaging::BitmapImage bitmap;
            bitmap.UriSource(Windows::Foundation::Uri(ToImageUri(imagePath)));
            image.Source(bitmap);
            image.Stretch(Microsoft::UI::Xaml::Media::Stretch::UniformToFill);
            image.Opacity(0.10);
            image.IsHitTestVisible(false);
            return true;
        }
        catch (...)
        {
            return false;
        }
    }

    Microsoft::UI::Xaml::GridLength PixelLength(double value)
    {
        return Microsoft::UI::Xaml::GridLength{ value, Microsoft::UI::Xaml::GridUnitType::Pixel };
    }

    Microsoft::UI::Xaml::GridLength StarLength()
    {
        return Microsoft::UI::Xaml::GridLength{ 1, Microsoft::UI::Xaml::GridUnitType::Star };
    }

    Microsoft::UI::Xaml::GridLength WeightedStarLength(double value)
    {
        return Microsoft::UI::Xaml::GridLength{ value, Microsoft::UI::Xaml::GridUnitType::Star };
    }

    Microsoft::UI::Xaml::GridLength AutoLength()
    {
        return Microsoft::UI::Xaml::GridLength{ 0, Microsoft::UI::Xaml::GridUnitType::Auto };
    }

    TextBlock MakeTextBlock(winrt::hstring const& value, double fontSize, Brush const& foreground)
    {
        TextBlock block;
        block.Text(value);
        block.FontSize(fontSize);
        block.Foreground(foreground);
        block.TextWrapping(Microsoft::UI::Xaml::TextWrapping::NoWrap);
        block.TextTrimming(Microsoft::UI::Xaml::TextTrimming::CharacterEllipsis);
        return block;
    }

    Grid MakeGeminiIconMark(double size)
    {
        Grid mark;
        mark.Width(size);
        mark.Height(size);
        mark.IsHitTestVisible(false);

        auto fallback = MakeTextBlock(L"\x2726", size * 0.78, ResourceBrush(L"AppAccentBrush"));
        fallback.FontFamily(FontFamily(L"Segoe UI Symbol"));
        fallback.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Center);
        fallback.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        fallback.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Center);
        mark.Children().Append(fallback);

        auto directory = ExecutableDirectory();
        if (!directory.empty())
        {
            auto iconPath = directory + L"\\assets\\gemini-icon.png";
            if (GetFileAttributesW(iconPath.c_str()) != INVALID_FILE_ATTRIBUTES)
            {
                Microsoft::UI::Xaml::Media::Imaging::BitmapImage bitmap;
                bitmap.UriSource(Windows::Foundation::Uri(ToImageUri(iconPath)));

                Image icon;
                icon.Width(size);
                icon.Height(size);
                icon.Stretch(Microsoft::UI::Xaml::Media::Stretch::Uniform);
                icon.Source(bitmap);
                icon.IsHitTestVisible(false);
                mark.Children().Append(icon);
            }
        }

        return mark;
    }

    FontIcon FluentIcon(wchar_t const* glyph, double fontSize, Brush const& foreground)
    {
        FontIcon icon;
        icon.FontFamily(FontFamily(L"Segoe Fluent Icons"));
        icon.FontSize(fontSize);
        icon.Glyph(glyph);
        icon.Foreground(foreground);
        icon.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Center);
        icon.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        return icon;
    }

    NavigationViewItem NavigationItem(
        winrt::hstring const& label,
        wchar_t const* tag,
        wchar_t const* glyph)
    {
        NavigationViewItem item;
        item.Content(winrt::box_value(label));
        item.Tag(winrt::box_value(tag));
        item.Icon(FluentIcon(glyph, 16, ResourceBrush(L"AppSecondaryTextBrush")));
        return item;
    }

    void AppendInfoRow(
        StackPanel const& panel,
        winrt::hstring const& label,
        winrt::hstring const& value)
    {
        Grid row;
        row.ColumnSpacing(16);
        row.Padding(Microsoft::UI::Xaml::Thickness{ 0, 6, 0, 6 });

        ColumnDefinition labelColumn;
        labelColumn.Width(PixelLength(176));
        row.ColumnDefinitions().Append(labelColumn);

        ColumnDefinition valueColumn;
        valueColumn.Width(StarLength());
        row.ColumnDefinitions().Append(valueColumn);

        auto labelText = MakeTextBlock(label, kSecondaryFontSize, ResourceBrush(L"AppSecondaryTextBrush"));
        auto valueText = MakeTextBlock(value, kBodyFontSize, ResourceBrush(L"AppTextBrush"));
        valueText.TextWrapping(Microsoft::UI::Xaml::TextWrapping::Wrap);
        Grid::SetColumn(valueText, 1);

        row.Children().Append(labelText);
        row.Children().Append(valueText);
        panel.Children().Append(row);
    }

    std::wstring FormatNumber(double value, int decimals = 0)
    {
        std::wstringstream stream;
        if (decimals > 0)
        {
            stream << std::fixed << std::setprecision(decimals) << value;
        }
        else
        {
            stream << static_cast<long long>(value);
        }
        return stream.str();
    }

    winrt::hstring H(std::wstring const& value)
    {
        return winrt::hstring(value.c_str());
    }

    std::wstring Truncate(std::wstring value, size_t maxLength)
    {
        if (value.size() <= maxLength)
        {
            return value;
        }

        return value.substr(0, maxLength - 1) + L"\x2026";
    }

    JsonObject ParseJsonObject(winrt::hstring const& json)
    {
        JsonObject result{ nullptr };
        if (!json.empty())
        {
            JsonObject::TryParse(json, result);
        }
        return result;
    }

    JsonObject GetJsonObject(JsonObject const& parent, wchar_t const* key)
    {
        if (!parent || !parent.HasKey(key))
        {
            return nullptr;
        }

        try
        {
            auto value = parent.GetNamedValue(key);
            if (value && value.ValueType() == JsonValueType::Object)
            {
                return value.GetObject();
            }
        }
        catch (...)
        {
        }
        return nullptr;
    }

    JsonArray GetJsonArray(JsonObject const& parent, wchar_t const* key)
    {
        if (!parent || !parent.HasKey(key))
        {
            return nullptr;
        }

        try
        {
            auto value = parent.GetNamedValue(key);
            if (value && value.ValueType() == JsonValueType::Array)
            {
                return value.GetArray();
            }
        }
        catch (...)
        {
        }
        return nullptr;
    }

    winrt::hstring JsonString(JsonObject const& object, wchar_t const* key, wchar_t const* fallback = L"--")
    {
        if (!object || !object.HasKey(key))
        {
            return fallback;
        }

        try
        {
            auto value = object.GetNamedValue(key);
            if (!value)
            {
                return fallback;
            }
            if (value.ValueType() == JsonValueType::String)
            {
                return value.GetString();
            }
            if (value.ValueType() == JsonValueType::Number)
            {
                return H(FormatNumber(value.GetNumber()));
            }
            if (value.ValueType() == JsonValueType::Boolean)
            {
                return value.GetBoolean() ? L"true" : L"false";
            }
        }
        catch (...)
        {
        }
        return fallback;
    }

    winrt::hstring JsonNumber(JsonObject const& object, wchar_t const* key, wchar_t const* fallback = L"0", int decimals = 0)
    {
        if (!object || !object.HasKey(key))
        {
            return fallback;
        }

        try
        {
            auto value = object.GetNamedValue(key);
            if (value && value.ValueType() == JsonValueType::Number)
            {
                return H(FormatNumber(value.GetNumber(), decimals));
            }
        }
        catch (...)
        {
        }
        return fallback;
    }

    double ReadJsonDouble(JsonObject const& object, wchar_t const* key, double fallback = 0.0)
    {
        if (!object || !object.HasKey(key))
        {
            return fallback;
        }

        try
        {
            auto value = object.GetNamedValue(key);
            if (value && value.ValueType() == JsonValueType::Number)
            {
                return value.GetNumber();
            }
        }
        catch (...)
        {
        }
        return fallback;
    }

    winrt::hstring JsonValuePreview(JsonObject const& object, wchar_t const* key, wchar_t const* fallback = L"--")
    {
        if (!object || !object.HasKey(key))
        {
            return fallback;
        }

        try
        {
            auto value = object.GetNamedValue(key);
            if (value)
            {
                return H(Truncate(value.Stringify().c_str(), 900));
            }
        }
        catch (...)
        {
        }
        return fallback;
    }

    void AppendPageHeader(StackPanel const& panel, winrt::hstring const& title, winrt::hstring const& subtitle)
    {
        StackPanel header;
        header.Spacing(4);

        auto titleText = MakeTextBlock(title, kTitleFontSize, ResourceBrush(L"AppTextBrush"));
        titleText.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        AutomationProperties::SetAutomationId(titleText, L"PageTitle");
        header.Children().Append(titleText);

        auto subtitleText = MakeTextBlock(subtitle, kSecondaryFontSize, ResourceBrush(L"AppSecondaryTextBrush"));
        subtitleText.TextWrapping(Microsoft::UI::Xaml::TextWrapping::Wrap);
        subtitleText.MaxLines(2);
        header.Children().Append(subtitleText);
        panel.Children().Append(header);
    }

    Border MakeFlatPanel()
    {
        Border panel;
        panel.Background(ResourceBrush(L"AppLayerBrush"));
        panel.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        panel.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        panel.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        panel.Padding(Microsoft::UI::Xaml::Thickness{ kPanelPadding });
        panel.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);
        return panel;
    }

    void AppendModeBar(StackPanel const& panel, std::initializer_list<winrt::hstring> labels)
    {
        Border modeFrame;
        modeFrame.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Left);
        modeFrame.Background(ResourceBrush(L"AppControlBrush"));
        modeFrame.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        modeFrame.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        modeFrame.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        modeFrame.Padding(Microsoft::UI::Xaml::Thickness{ 2 });
        AutomationProperties::SetAutomationId(modeFrame, L"SegmentedModeBar");

        StackPanel modes;
        modes.Orientation(Orientation::Horizontal);
        modes.Spacing(2);

        uint32_t index = 0;
        for (auto const& label : labels)
        {
            Button button;
            button.Height(28);
            button.MinWidth(92);
            button.Padding(Microsoft::UI::Xaml::Thickness{ 12, 0, 12, 0 });
            button.FontSize(kSecondaryFontSize);
            button.Content(winrt::box_value(label));
            button.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
            button.BorderBrush(index == 0 ? ResourceBrush(L"AppAccentBrush") : ColorBrush(0, 0, 0, 0));
            button.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
            button.Background(ResourceBrush(index == 0 ? L"AppSelectedBrush" : L"AppControlBrush"));
            if (index == 0)
            {
                AutomationProperties::SetAutomationId(button, L"SegmentedModeBar");
            }
            modes.Children().Append(button);
            ++index;
        }

        modeFrame.Child(modes);
        panel.Children().Append(modeFrame);
    }

    Button MakeCommandButton(winrt::hstring const& label, wchar_t const* automationId)
    {
        Button button;
        button.Height(32);
        button.MinWidth(112);
        button.Padding(Microsoft::UI::Xaml::Thickness{ 12, 0, 12, 0 });
        button.FontSize(kBodyFontSize);
        button.Content(winrt::box_value(label));
        button.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        button.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        button.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        button.Background(ResourceBrush(L"AppControlBrush"));
        AutomationProperties::SetAutomationId(button, automationId);
        AutomationProperties::SetName(button, label);
        return button;
    }

    void AppendCommandRow(StackPanel const& panel, std::initializer_list<Button> buttons)
    {
        StackPanel row;
        row.Orientation(Orientation::Horizontal);
        row.Spacing(8);
        row.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Left);
        AutomationProperties::SetAutomationId(row, L"ServerCommandRow");
        for (auto const& button : buttons)
        {
            row.Children().Append(button);
        }
        panel.Children().Append(row);
    }

    void AppendMetricCell(Grid const& grid, int row, int column, winrt::hstring const& label, winrt::hstring const& value)
    {
        Border cell = MakeFlatPanel();
        cell.MinHeight(72);

        StackPanel stack;
        stack.Spacing(6);
        stack.Children().Append(MakeTextBlock(label, kSecondaryFontSize, ResourceBrush(L"AppSecondaryTextBrush")));
        auto valueText = MakeTextBlock(value, kTitleFontSize, ResourceBrush(L"AppTextBrush"));
        valueText.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        valueText.TextWrapping(Microsoft::UI::Xaml::TextWrapping::Wrap);
        valueText.MaxLines(2);
        stack.Children().Append(valueText);
        cell.Child(stack);
        Grid::SetRow(cell, row);
        Grid::SetColumn(cell, column);
        grid.Children().Append(cell);
    }

    void AppendMetricRow(
        StackPanel const& panel,
        winrt::hstring const& label1,
        winrt::hstring const& value1,
        winrt::hstring const& label2,
        winrt::hstring const& value2,
        winrt::hstring const& label3,
        winrt::hstring const& value3,
        winrt::hstring const& label4,
        winrt::hstring const& value4)
    {
        Grid grid;
        grid.ColumnSpacing(12);
        grid.RowSpacing(12);
        for (int i = 0; i < 2; ++i)
        {
            ColumnDefinition column;
            column.Width(StarLength());
            grid.ColumnDefinitions().Append(column);
        }
        for (int i = 0; i < 2; ++i)
        {
            RowDefinition row;
            row.Height(AutoLength());
            grid.RowDefinitions().Append(row);
        }
        AppendMetricCell(grid, 0, 0, label1, value1);
        AppendMetricCell(grid, 0, 1, label2, value2);
        AppendMetricCell(grid, 1, 0, label3, value3);
        AppendMetricCell(grid, 1, 1, label4, value4);
        panel.Children().Append(grid);
    }

    void AppendCell(Grid const& row, int column, winrt::hstring const& text, double fontSize, bool rightAligned = false)
    {
        auto cell = MakeTextBlock(text, fontSize, ResourceBrush(L"AppTextBrush"));
        cell.TextTrimming(Microsoft::UI::Xaml::TextTrimming::CharacterEllipsis);
        cell.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        if (rightAligned)
        {
            cell.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Right);
            cell.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);
        }
        Grid::SetColumn(cell, column);
        row.Children().Append(cell);
    }

    void AppendHeaderCell(Grid const& row, int column, winrt::hstring const& text, bool rightAligned = false)
    {
        auto cell = MakeTextBlock(text, 12, ResourceBrush(L"AppSecondaryTextBrush"));
        cell.FontWeight(Microsoft::UI::Text::FontWeights::Medium());
        cell.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        if (rightAligned)
        {
            cell.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Right);
            cell.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);
        }
        Grid::SetColumn(cell, column);
        row.Children().Append(cell);
    }

    void AppendShareBarCell(Grid const& row, int column, double value, double maxValue, wchar_t const* automationId)
    {
        double percent = maxValue > 0 ? std::clamp((value / maxValue) * 100.0, 0.0, 100.0) : 0.0;

        Grid share;
        share.ColumnSpacing(8);

        ColumnDefinition barColumn;
        barColumn.Width(StarLength());
        share.ColumnDefinitions().Append(barColumn);

        ColumnDefinition valueColumn;
        valueColumn.Width(PixelLength(44));
        share.ColumnDefinitions().Append(valueColumn);

        ProgressBar bar;
        bar.Minimum(0);
        bar.Maximum(100);
        bar.Value(percent);
        bar.Height(6);
        bar.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        bar.Foreground(ResourceBrush(L"AppAccentBrush"));
        bar.Background(ResourceBrush(L"AppControlBrush"));
        AutomationProperties::SetAutomationId(bar, automationId);

        auto label = MakeTextBlock(H(FormatNumber(percent) + L"%"), kCaptionFontSize, ResourceBrush(L"AppSecondaryTextBrush"));
        label.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Right);
        label.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);
        label.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        Grid::SetColumn(label, 1);

        share.Children().Append(bar);
        share.Children().Append(label);
        Grid::SetColumn(share, column);
        row.Children().Append(share);
    }

    void AppendNativeSummaryStrip(
        StackPanel const& panel,
        wchar_t const* automationId,
        std::initializer_list<std::pair<winrt::hstring, winrt::hstring>> cells)
    {
        Border host;
        host.Background(ColorBrush(1, 0, 0, 0));
        host.BorderThickness(Microsoft::UI::Xaml::Thickness{ 0 });
        host.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);
        AutomationProperties::SetAutomationId(host, automationId);

        Grid summary;
        summary.ColumnSpacing(8);
        AutomationProperties::SetAutomationId(summary, automationId);

        for (uint32_t i = 0; i < cells.size(); ++i)
        {
            ColumnDefinition column;
            column.Width(StarLength());
            summary.ColumnDefinitions().Append(column);
        }

        uint32_t columnIndex = 0;
        for (auto const& cell : cells)
        {
            Border frame;
            frame.MinHeight(56);
            frame.Background(ResourceBrush(L"AppSurfaceBrush"));
            frame.BorderBrush(ResourceBrush(L"AppBorderBrush"));
            frame.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
            frame.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
            frame.Padding(Microsoft::UI::Xaml::Thickness{ 12, 8, 12, 8 });

            StackPanel stack;
            stack.Spacing(4);
            stack.Children().Append(MakeTextBlock(cell.first, kCaptionFontSize, ResourceBrush(L"AppSecondaryTextBrush")));
            auto valueText = MakeTextBlock(cell.second, kBodyFontSize, ResourceBrush(L"AppTextBrush"));
            valueText.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
            valueText.TextTrimming(Microsoft::UI::Xaml::TextTrimming::CharacterEllipsis);
            stack.Children().Append(valueText);

            frame.Child(stack);
            Grid::SetColumn(frame, columnIndex++);
            summary.Children().Append(frame);
        }

        host.Child(summary);
        panel.Children().Append(host);
    }

    Grid MakeRequestGridRow()
    {
        Grid row;
        row.ColumnSpacing(16);
        row.MinHeight(36);

        for (auto width : { 1.05, 1.35, 0.70, 0.70, 0.80, 1.90 })
        {
            ColumnDefinition column;
            column.Width(WeightedStarLength(width));
            row.ColumnDefinitions().Append(column);
        }
        return row;
    }

    Grid MakeQuotaGridRow()
    {
        Grid row;
        row.ColumnSpacing(16);
        row.MinHeight(38);

        for (auto width : { 1.05, 0.70, 0.82, 1.25 })
        {
            ColumnDefinition column;
            column.Width(WeightedStarLength(width));
            row.ColumnDefinitions().Append(column);
        }
        return row;
    }

    Grid MakeModelUsageGridRow()
    {
        Grid row;
        row.ColumnSpacing(16);
        row.MinHeight(38);

        for (auto width : { 1.45, 0.68, 0.82, 0.82, 0.82, 1.18 })
        {
            ColumnDefinition column;
            column.Width(WeightedStarLength(width));
            row.ColumnDefinitions().Append(column);
        }
        return row;
    }

    void AppendRecentRequests(StackPanel const& panel, JsonObject const& stats, bool chinese)
    {
        Border listPanel = MakeFlatPanel();
        AutomationProperties::SetAutomationId(listPanel, L"RecentRequestList");

        StackPanel list;
        list.Spacing(kPanelSpacing);
        auto sectionTitle = MakeTextBlock(chinese ? L"最近请求" : L"Recent Requests", kBodyFontSize, ResourceBrush(L"AppTextBrush"));
        sectionTitle.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        AutomationProperties::SetAutomationId(sectionTitle, L"RecentRequestList");
        list.Children().Append(sectionTitle);

        auto header = MakeRequestGridRow();
        AppendHeaderCell(header, 0, chinese ? L"时间" : L"Time");
        AppendHeaderCell(header, 1, chinese ? L"模型" : L"Model");
        AppendHeaderCell(header, 2, chinese ? L"Token" : L"Tokens", true);
        AppendHeaderCell(header, 3, chinese ? L"耗时" : L"ms", true);
        AppendHeaderCell(header, 4, chinese ? L"状态" : L"Status");
        AppendHeaderCell(header, 5, chinese ? L"端点 / ID" : L"Endpoint / ID");
        list.Children().Append(header);

        auto requests = GetJsonArray(stats, L"recent_requests");
        if (!requests || requests.Size() == 0)
        {
            list.Children().Append(MakeTextBlock(
                chinese ? L"暂无请求；启动服务并发起一次 API 调用后这里会显示真实明细。"
                        : L"No requests yet. Start the service and send an API call to populate real details.",
                12,
                ResourceBrush(L"AppSecondaryTextBrush")));
        }
        else
        {
            uint32_t count = std::min<uint32_t>(requests.Size(), 6);
            for (uint32_t i = 0; i < count; ++i)
            {
                JsonObject request{ nullptr };
                try
                {
                    request = requests.GetAt(i).GetObject();
                }
                catch (...)
                {
                    continue;
                }

                auto row = MakeRequestGridRow();
                AppendCell(row, 0, JsonString(request, L"time_str"), 12);
                AppendCell(row, 1, JsonString(request, L"model"), 12);
                AppendCell(row, 2, JsonNumber(request, L"total_tokens"), 12, true);
                AppendCell(row, 3, JsonNumber(request, L"duration_ms", L"--", 1), 12, true);
                AppendCell(row, 4, JsonString(request, L"status"), 12);
                auto endpoint = std::wstring(JsonString(request, L"endpoint").c_str());
                auto id = std::wstring(JsonString(request, L"id").c_str());
                AppendCell(row, 5, H(Truncate(endpoint + L"  " + id, 96)), 12);
                list.Children().Append(row);
            }
        }

        listPanel.Child(list);
        panel.Children().Append(listPanel);
    }

    void AppendBodyPreview(StackPanel const& panel, JsonObject const& stats, bool chinese)
    {
        Border bodyPanel = MakeFlatPanel();
        AutomationProperties::SetAutomationId(bodyPanel, L"RequestBodyPreviewPanel");

        StackPanel root;
        root.Spacing(12);
        auto title = MakeTextBlock(chinese ? L"请求体 / 返回体预览" : L"Request / Response Body Preview", kBodyFontSize, ResourceBrush(L"AppTextBrush"));
        title.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        root.Children().Append(title);

        JsonObject request{ nullptr };
        auto requests = GetJsonArray(stats, L"recent_requests");
        if (requests && requests.Size() > 0)
        {
            try
            {
                request = requests.GetAt(0).GetObject();
            }
            catch (...)
            {
            }
        }

        Grid grid;
        grid.ColumnSpacing(16);
        ColumnDefinition left;
        left.Width(StarLength());
        ColumnDefinition right;
        right.Width(StarLength());
        grid.ColumnDefinitions().Append(left);
        grid.ColumnDefinitions().Append(right);

        auto appendPreviewColumn = [&](int column, winrt::hstring const& heading, winrt::hstring const& content, wchar_t const* automationId)
        {
            StackPanel stack;
            stack.Spacing(6);
            stack.Children().Append(MakeTextBlock(heading, kSecondaryFontSize, ResourceBrush(L"AppSecondaryTextBrush")));
            auto preview = MakeTextBlock(content, kCaptionFontSize, ResourceBrush(L"AppTextBrush"));
            preview.FontFamily(FontFamily(L"Consolas"));
            preview.TextWrapping(Microsoft::UI::Xaml::TextWrapping::Wrap);
            preview.MaxHeight(160);
            AutomationProperties::SetAutomationId(preview, automationId);
            stack.Children().Append(preview);
            Grid::SetColumn(stack, column);
            grid.Children().Append(stack);
        };

        appendPreviewColumn(
            0,
            chinese ? L"真实请求体" : L"Raw Request Body",
            JsonValuePreview(request, L"request_body", chinese ? L"暂无捕获的请求体。" : L"No captured request body yet."),
            L"RequestBodyPreview");
        appendPreviewColumn(
            1,
            chinese ? L"真实返回体" : L"Raw Response Body",
            JsonValuePreview(request, L"response_body", chinese ? L"暂无捕获的返回体。" : L"No captured response body yet."),
            L"ResponseBodyPreview");

        root.Children().Append(grid);
        bodyPanel.Child(root);
        panel.Children().Append(bodyPanel);
    }

    void AppendTrendPreview(StackPanel const& panel, JsonObject const& stats, bool chinese)
    {
        Border trendPanel = MakeFlatPanel();
        AutomationProperties::SetAutomationId(trendPanel, L"TrendPreviewPanel");

        StackPanel root;
        root.Spacing(kPanelSpacing);
        auto title = MakeTextBlock(chinese ? L"额度与运维总量" : L"Quota And Operations", kBodyFontSize, ResourceBrush(L"AppTextBrush"));
        title.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        AutomationProperties::SetAutomationId(title, L"TrendPreviewPanel");
        root.Children().Append(title);

        auto hourly = GetJsonArray(stats, L"hourly_stats");
        std::vector<JsonObject> visibleRows;
        double totalTokens = 0;
        double totalRequests = 0;
        double latestTokens = 0;
        double peakTokens = 1.0;
        if (hourly && hourly.Size() > 0)
        {
            uint32_t start = hourly.Size() > 6 ? hourly.Size() - 6 : 0;
            for (uint32_t i = start; i < hourly.Size(); ++i)
            {
                try
                {
                    auto item = hourly.GetAt(i).GetObject();
                    auto tokens = ReadJsonDouble(item, L"tokens", 0.0);
                    auto requests = ReadJsonDouble(item, L"requests", 0.0);
                    visibleRows.push_back(item);
                    totalTokens += tokens;
                    totalRequests += requests;
                    latestTokens = tokens;
                    peakTokens = tokens > peakTokens ? tokens : peakTokens;
                }
                catch (...)
                {
                }
            }
        }

        AppendNativeSummaryStrip(
            root,
            L"NativeQuotaSummary",
            {
                { chinese ? L"最新 Token" : L"Latest tokens", H(FormatNumber(latestTokens)) },
                { chinese ? L"区间总量" : L"Range total", H(FormatNumber(totalTokens)) },
                { chinese ? L"请求量" : L"Requests", H(FormatNumber(totalRequests)) },
                { chinese ? L"单次均值" : L"Avg/request", H(FormatNumber(totalRequests > 0 ? totalTokens / totalRequests : 0, 1)) },
            });

        Border tableFrame;
        tableFrame.Background(ResourceBrush(L"AppSurfaceBrush"));
        tableFrame.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        tableFrame.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        tableFrame.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        tableFrame.Padding(Microsoft::UI::Xaml::Thickness{ 10, 6, 10, 6 });
        AutomationProperties::SetAutomationId(tableFrame, L"NativeQuotaTable");

        StackPanel rows;
        rows.Spacing(4);

        auto header = MakeQuotaGridRow();
        AppendHeaderCell(header, 0, chinese ? L"时间" : L"Time");
        AppendHeaderCell(header, 1, chinese ? L"请求" : L"Requests", true);
        AppendHeaderCell(header, 2, chinese ? L"Token" : L"Tokens", true);
        AppendHeaderCell(header, 3, chinese ? L"额度占比" : L"Quota Share");
        rows.Children().Append(header);

        if (visibleRows.empty())
        {
            rows.Children().Append(MakeTextBlock(
                chinese ? L"暂无趋势数据；请求发生后将按小时记录请求数和 Token 总量。"
                        : L"No trend data yet. Hourly request and token totals appear after traffic.",
                12,
                ResourceBrush(L"AppSecondaryTextBrush")));
        }
        else
        {
            for (auto const& item : visibleRows)
            {
                auto row = MakeQuotaGridRow();
                AppendCell(row, 0, JsonString(item, L"hour"), 12);
                AppendCell(row, 1, JsonNumber(item, L"requests"), 12, true);
                AppendCell(row, 2, JsonNumber(item, L"tokens"), 12, true);
                AppendShareBarCell(row, 3, ReadJsonDouble(item, L"tokens", 0.0), peakTokens, L"NativeQuotaShareBar");
                rows.Children().Append(row);
            }
        }

        tableFrame.Child(rows);
        root.Children().Append(tableFrame);
        trendPanel.Child(root);
        panel.Children().Append(trendPanel);
    }

    void AppendModelUsageTable(StackPanel const& panel, JsonObject const& stats, bool chinese)
    {
        Border tablePanel = MakeFlatPanel();
        AutomationProperties::SetAutomationId(tablePanel, L"NativeModelUsageTable");

        StackPanel root;
        root.Spacing(kPanelSpacing);
        AutomationProperties::SetAutomationId(root, L"NativeModelUsageTable");
        auto title = MakeTextBlock(chinese ? L"模型用量" : L"Model Usage", kBodyFontSize, ResourceBrush(L"AppTextBrush"));
        title.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        root.Children().Append(title);

        auto modelStats = GetJsonObject(stats, L"model_stats");
        struct ModelRow
        {
            std::wstring name;
            JsonObject stats{ nullptr };
            double tokens{ 0 };
            double requests{ 0 };
            double errors{ 0 };
        };

        std::vector<ModelRow> rows;
        if (modelStats)
        {
            for (auto const& pair : modelStats)
            {
                try
                {
                    auto object = pair.Value().GetObject();
                    rows.push_back(ModelRow{
                        std::wstring(pair.Key().c_str()),
                        object,
                        ReadJsonDouble(object, L"total_tokens", 0.0),
                        ReadJsonDouble(object, L"requests", 0.0),
                        ReadJsonDouble(object, L"errors", 0.0) });
                }
                catch (...)
                {
                }
            }
        }

        std::sort(rows.begin(), rows.end(), [](ModelRow const& left, ModelRow const& right)
        {
            return left.tokens > right.tokens;
        });

        double peakTokens = 1.0;
        double totalTokens = 0;
        double totalRequests = 0;
        double totalErrors = 0;
        for (auto const& row : rows)
        {
            peakTokens = row.tokens > peakTokens ? row.tokens : peakTokens;
            totalTokens += row.tokens;
            totalRequests += row.requests;
            totalErrors += row.errors;
        }

        AppendNativeSummaryStrip(
            root,
            L"NativeModelUsageSummary",
            {
                { chinese ? L"模型数" : L"Models", H(FormatNumber(static_cast<double>(rows.size()))) },
                { chinese ? L"请求量" : L"Requests", H(FormatNumber(totalRequests)) },
                { chinese ? L"Token 总量" : L"Total tokens", H(FormatNumber(totalTokens)) },
                { chinese ? L"错误数" : L"Errors", H(FormatNumber(totalErrors)) },
            });

        Border tableFrame;
        tableFrame.Background(ResourceBrush(L"AppSurfaceBrush"));
        tableFrame.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        tableFrame.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        tableFrame.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        tableFrame.Padding(Microsoft::UI::Xaml::Thickness{ 10, 6, 10, 6 });

        StackPanel tableRows;
        tableRows.Spacing(4);

        auto header = MakeModelUsageGridRow();
        AppendHeaderCell(header, 0, chinese ? L"模型" : L"Model");
        AppendHeaderCell(header, 1, chinese ? L"请求" : L"Requests", true);
        AppendHeaderCell(header, 2, chinese ? L"输入" : L"Input", true);
        AppendHeaderCell(header, 3, chinese ? L"输出" : L"Output", true);
        AppendHeaderCell(header, 4, chinese ? L"总量" : L"Total", true);
        AppendHeaderCell(header, 5, chinese ? L"占比" : L"Share");
        tableRows.Children().Append(header);

        if (rows.empty())
        {
            tableRows.Children().Append(MakeTextBlock(
                chinese ? L"暂无模型统计；真实请求完成后这里会显示模型用量。"
                        : L"No model statistics yet. Real model usage appears after requests complete.",
                12,
                ResourceBrush(L"AppSecondaryTextBrush")));
        }
        else
        {
            uint32_t count = std::min<uint32_t>(static_cast<uint32_t>(rows.size()), 8);
            for (uint32_t i = 0; i < count; ++i)
            {
                auto const& item = rows[i];
                auto row = MakeModelUsageGridRow();
                AppendCell(row, 0, H(Truncate(item.name, 48)), 12);
                AppendCell(row, 1, JsonNumber(item.stats, L"requests"), 12, true);
                AppendCell(row, 2, JsonNumber(item.stats, L"prompt_tokens"), 12, true);
                AppendCell(row, 3, JsonNumber(item.stats, L"completion_tokens"), 12, true);
                AppendCell(row, 4, JsonNumber(item.stats, L"total_tokens"), 12, true);
                AppendShareBarCell(row, 5, item.tokens, peakTokens, L"NativeModelShareBar");
                tableRows.Children().Append(row);
            }
        }

        tableFrame.Child(tableRows);
        root.Children().Append(tableFrame);
        tablePanel.Child(root);
        panel.Children().Append(tablePanel);
    }
}

namespace winrt::Gemini2API::implementation
{
    winrt::hstring MainWindow::Text(wchar_t const* key) const
    {
        std::wstring_view name{ key };
        if (!m_useChinese)
        {
            if (name == L"brand_subtitle") return L"Native Windows shell";
            if (name == L"stopped") return L"Stopped";
            if (name == L"overview_title") return L"Overview";
            if (name == L"overview_subtitle") return L"Service health and native shell summary";
            if (name == L"server_title") return L"Server";
            if (name == L"server_subtitle") return L"Backend process controls and local endpoint status";
            if (name == L"cookies_title") return L"Cookies";
            if (name == L"cookies_subtitle") return L"Cookie sources, browser integration, and validation";
            if (name == L"streaming_title") return L"Streaming";
            if (name == L"streaming_subtitle") return L"Live request stream, response timing, and body inspection";
            if (name == L"models_title") return L"Models";
            if (name == L"models_subtitle") return L"Model availability, token accounting, and capability metadata";
            if (name == L"logs_title") return L"Logs";
            if (name == L"logs_subtitle") return L"Operational events, proxy decisions, and request details";
            if (name == L"settings_title") return L"Settings";
            if (name == L"settings_subtitle") return L"Language, refresh cadence, proxy, and security settings";
            if (name == L"runtime") return L"Runtime";
            if (name == L"runtime_value") return L"Windows App SDK with WinUI 3";
            if (name == L"backdrop") return L"Backdrop";
            if (name == L"backdrop_value") return L"Mica with Acrylic fallback";
            if (name == L"backend") return L"Backend";
            if (name == L"backend_value") return L"Existing Gemini2API Python server";
            if (name == L"endpoint") return L"Endpoint";
            if (name == L"process_model") return L"Process model";
            if (name == L"process_model_value") return L"Rust supervisor preferred, native fallback if unavailable";
            if (name == L"refresh_cadence") return L"Refresh cadence";
            if (name == L"refresh_cadence_value") return L"Real-time refresh target: 1 second";
            if (name == L"manual_import") return L"Manual import";
            if (name == L"manual_import_value") return L"Paste, file import, and network export parsing";
            if (name == L"edge_extension") return L"Edge extension";
            if (name == L"edge_extension_value") return L"Capture from Gemini web and push to local service";
            if (name == L"internal_browser") return L"Internal browser";
            if (name == L"internal_browser_value") return L"Isolated login environment for controlled cookie extraction";
            if (name == L"request_body") return L"Request body";
            if (name == L"request_body_value") return L"Raw payload viewer backed by request logs";
            if (name == L"response_body") return L"Response body";
            if (name == L"response_body_value") return L"Raw response and error details";
            if (name == L"latency") return L"Latency";
            if (name == L"latency_value") return L"Per-request timing with one-second live refresh";
            if (name == L"model_source") return L"Model source";
            if (name == L"model_source_value") return L"Existing backend model endpoints";
            if (name == L"token_metrics") return L"Token metrics";
            if (name == L"token_metrics_value") return L"Request, response, and total token estimates";
            if (name == L"operations") return L"Operations";
            if (name == L"operations_value") return L"Daily totals, running totals, and service-level counters";
            if (name == L"proxy") return L"Proxy";
            if (name == L"proxy_value") return L"Per-request route, retry, and failure reason";
            if (name == L"bodies") return L"Bodies";
            if (name == L"bodies_value") return L"Raw request and response drill-down";
            if (name == L"retention") return L"Retention";
            if (name == L"retention_value") return L"Local diagnostics with explicit clear action";
            if (name == L"language") return L"Language";
            if (name == L"language_value") return L"English and Simplified Chinese are separate UI modes";
            if (name == L"refresh") return L"Refresh";
            if (name == L"refresh_value") return L"One-second live status and request polling target";
            if (name == L"proxy_settings_value") return L"Backend-aligned routing and validation controls";
            if (name == L"visual_layer") return L"Visual layer";
            if (name == L"visual_layer_value") return L"Optional local image via GEMINI2API_VISUAL_IMAGE; disabled by default";
            if (name == L"language_button") return L"中文";
        }
        else
        {
            if (name == L"brand_subtitle") return L"原生 Windows 外壳";
            if (name == L"stopped") return L"已停止";
            if (name == L"overview_title") return L"概览";
            if (name == L"overview_subtitle") return L"服务健康与原生外壳摘要";
            if (name == L"server_title") return L"服务";
            if (name == L"server_subtitle") return L"后端进程控制与本地端点状态";
            if (name == L"cookies_title") return L"Cookie";
            if (name == L"cookies_subtitle") return L"Cookie 来源、浏览器联动与校验";
            if (name == L"streaming_title") return L"实时请求";
            if (name == L"streaming_subtitle") return L"实时请求流、响应耗时与正文检查";
            if (name == L"models_title") return L"模型";
            if (name == L"models_subtitle") return L"模型可用性、Token 计算与能力元数据";
            if (name == L"logs_title") return L"日志";
            if (name == L"logs_subtitle") return L"运维事件、代理决策与请求明细";
            if (name == L"settings_title") return L"设置";
            if (name == L"settings_subtitle") return L"语言、刷新周期、代理与安全设置";
            if (name == L"runtime") return L"运行时";
            if (name == L"runtime_value") return L"Windows App SDK 与 WinUI 3";
            if (name == L"backdrop") return L"背景材质";
            if (name == L"backdrop_value") return L"Mica，失败时回退 Acrylic";
            if (name == L"backend") return L"后端";
            if (name == L"backend_value") return L"现有 Gemini2API 服务";
            if (name == L"endpoint") return L"端点";
            if (name == L"process_model") return L"进程模型";
            if (name == L"process_model_value") return L"优先 Rust supervisor，缺失时原生回退";
            if (name == L"refresh_cadence") return L"刷新周期";
            if (name == L"refresh_cadence_value") return L"实时刷新目标：1 秒";
            if (name == L"manual_import") return L"手动导入";
            if (name == L"manual_import_value") return L"粘贴、文件导入与网络导出解析";
            if (name == L"edge_extension") return L"Edge 插件";
            if (name == L"edge_extension_value") return L"从 Gemini 网页端捕获并推送到本地服务";
            if (name == L"internal_browser") return L"内部浏览器";
            if (name == L"internal_browser_value") return L"隔离登录环境，用于受控提取 Cookie";
            if (name == L"request_body") return L"请求体";
            if (name == L"request_body_value") return L"由请求日志支撑的原始载荷查看";
            if (name == L"response_body") return L"返回体";
            if (name == L"response_body_value") return L"原始响应与错误明细";
            if (name == L"latency") return L"耗时";
            if (name == L"latency_value") return L"逐请求耗时与 1 秒实时刷新";
            if (name == L"model_source") return L"模型来源";
            if (name == L"model_source_value") return L"现有后端模型端点";
            if (name == L"token_metrics") return L"Token 指标";
            if (name == L"token_metrics_value") return L"请求、返回与总量估算";
            if (name == L"operations") return L"运维总量";
            if (name == L"operations_value") return L"每日总量、运行总量与服务级计数";
            if (name == L"proxy") return L"代理";
            if (name == L"proxy_value") return L"逐请求路由、重试与失败原因";
            if (name == L"bodies") return L"正文";
            if (name == L"bodies_value") return L"请求与返回的原始明细";
            if (name == L"retention") return L"保留";
            if (name == L"retention_value") return L"本地诊断，带显式清除操作";
            if (name == L"language") return L"语言";
            if (name == L"language_value") return L"英文与简体中文是独立界面模式";
            if (name == L"refresh") return L"刷新";
            if (name == L"refresh_value") return L"1 秒状态与请求轮询目标";
            if (name == L"proxy_settings_value") return L"与后端一致的路由和校验控制";
            if (name == L"visual_layer") return L"视觉层";
            if (name == L"visual_layer_value") return L"可通过 GEMINI2API_VISUAL_IMAGE 加载本地图片，默认关闭";
            if (name == L"language_button") return L"EN";
        }
        return key;
    }

    MainWindow::MainWindow()
    {
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: constructing");
        Title(L"Gemini2API");
        m_cachedStatus.baseUrl = L"http://127.0.0.1:18081";
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: BuildLayout start");
        BuildLayout();
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: BuildLayout complete");
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: applying Windows 11 backdrop and custom titlebar");
        ApplySystemBackdrop();
        ExtendsContentIntoTitleBar(true);
        SetTitleBar(m_appTitleBar);
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: Windows 11 shell chrome applied");

        ::Gemini2API::WriteRuntimeLog(L"MainWindow: Navigate home start");
        NavigateTo(L"home");
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: Navigate home complete");
        StartLiveRefresh();
        SetBackendStatus(Text(L"stopped"), false);
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: constructed");
    }

    void MainWindow::BuildLayout()
    {
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: creating root grid");
        Grid shell;
        shell.Background(ResourceBrush(L"AppSurfaceBrush"));

        Image personalVisualLayer;
        if (TryConfigurePersonalVisualLayer(personalVisualLayer))
        {
            shell.Children().Append(personalVisualLayer);
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: optional personal visual layer enabled");
        }

        Microsoft::UI::Xaml::Shapes::Rectangle acrylicTint;
        acrylicTint.Fill(ResourceBrush(L"AppSurfaceBrush"));
        acrylicTint.IsHitTestVisible(false);
        shell.Children().Append(acrylicTint);

        Grid root;
        root.Background(ResourceBrush(L"AppSurfaceBrush"));

        ColumnDefinition navColumn;
        navColumn.Width(PixelLength(kNavWidth));
        root.ColumnDefinitions().Append(navColumn);

        ColumnDefinition appColumn;
        appColumn.Width(StarLength());
        root.ColumnDefinitions().Append(appColumn);

        Grid rail;
        rail.Background(ResourceBrush(L"AppSurfaceBrush"));
        rail.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        rail.BorderThickness(Microsoft::UI::Xaml::Thickness{ 0, 0, 1, 0 });

        StackPanel railItems;
        railItems.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Top);

        auto appendNavItem = [&](winrt::hstring const& tag, wchar_t const* glyph)
        {
            Border item;
            item.Width(kNavWidth);
            item.Height(kNavWidth);
            item.Tag(winrt::box_value(tag));
            item.Background(ResourceBrush(tag == m_currentTag ? L"AppSelectedBrush" : L"AppSurfaceBrush"));
            item.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ 0 });
            auto navAutomationName = std::wstring(tag.c_str());
            if (!navAutomationName.empty() && navAutomationName[0] >= L'a' && navAutomationName[0] <= L'z')
            {
                navAutomationName[0] = static_cast<wchar_t>(navAutomationName[0] - L'a' + L'A');
            }
            AutomationProperties::SetAutomationId(item, H(L"Nav" + navAutomationName + L"Button"));
            AutomationProperties::SetName(item, tag);

            Grid itemGrid;
            ColumnDefinition indicatorColumn;
            indicatorColumn.Width(PixelLength(3));
            itemGrid.ColumnDefinitions().Append(indicatorColumn);
            ColumnDefinition iconColumn;
            iconColumn.Width(StarLength());
            itemGrid.ColumnDefinitions().Append(iconColumn);

            Microsoft::UI::Xaml::Shapes::Rectangle indicator;
            indicator.Width(3);
            indicator.Height(24);
            indicator.RadiusX(1.5);
            indicator.RadiusY(1.5);
            indicator.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
            indicator.Fill(tag == m_currentTag ? ResourceBrush(L"AppAccentBrush") : ColorBrush(0, 0, 0, 0));

            auto icon = MakeTextBlock(glyph, 16, tag == m_currentTag ? ResourceBrush(L"AppTextBrush") : ResourceBrush(L"AppSecondaryTextBrush"));
            icon.FontFamily(FontFamily(L"Segoe Fluent Icons"));
            icon.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Center);
            icon.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
            icon.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Center);
            Grid::SetColumn(icon, 1);

            itemGrid.Children().Append(indicator);
            itemGrid.Children().Append(icon);
            item.Child(itemGrid);

            item.PointerEntered([this, item, tag](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::Input::PointerRoutedEventArgs const&)
            {
                if (tag != m_currentTag)
                {
                    item.Background(ResourceBrush(L"AppHoverBrush"));
                }
            });

            item.PointerExited([this](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::Input::PointerRoutedEventArgs const&)
            {
                UpdateNavigationState();
            });

            item.Tapped([this, tag](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::Input::TappedRoutedEventArgs const&)
            {
                NavigateTo(tag);
            });

            railItems.Children().Append(item);
            m_navItems.push_back(item);
            m_navTags.push_back(tag);
        };

        appendNavItem(L"home", L"\xE80F");
        appendNavItem(L"server", L"\xE768");
        appendNavItem(L"cookies", L"\xE774");
        appendNavItem(L"streaming", L"\xE724");
        appendNavItem(L"models", L"\xE8B7");
        appendNavItem(L"logs", L"\xE8A5");
        appendNavItem(L"settings", L"\xE713");
        rail.Children().Append(railItems);

        Grid appSurface;
        Grid::SetColumn(appSurface, 1);

        RowDefinition titleRow;
        titleRow.Height(PixelLength(kTitleBarHeight));
        appSurface.RowDefinitions().Append(titleRow);

        RowDefinition contentRow;
        contentRow.Height(StarLength());
        appSurface.RowDefinitions().Append(contentRow);

        m_appTitleBar = Grid();
        m_appTitleBar.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        m_appTitleBar.BorderThickness(Microsoft::UI::Xaml::Thickness{ 0, 0, 0, 1 });
        m_appTitleBar.ColumnSpacing(12);

        ColumnDefinition brandColumn;
        brandColumn.Width(AutoLength());
        m_appTitleBar.ColumnDefinitions().Append(brandColumn);

        ColumnDefinition dragColumn;
        dragColumn.Width(StarLength());
        m_appTitleBar.ColumnDefinitions().Append(dragColumn);

        ColumnDefinition statusColumn;
        statusColumn.Width(AutoLength());
        m_appTitleBar.ColumnDefinitions().Append(statusColumn);

        StackPanel brandStack;
        brandStack.Margin(Microsoft::UI::Xaml::Thickness{ kPagePaddingX, 0, 0, 0 });
        brandStack.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        brandStack.Orientation(Orientation::Horizontal);
        brandStack.Spacing(8);

        Border accentBox;
        accentBox.Width(24);
        accentBox.Height(24);
        accentBox.Background(ColorBrush(0, 0, 0, 0));
        accentBox.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        accentBox.Child(MakeGeminiIconMark(22));

        m_titleText = MakeTextBlock(L"Gemini2API", kTitleFontSize, ResourceBrush(L"AppTextBrush"));
        m_titleText.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());

        brandStack.Children().Append(accentBox);
        brandStack.Children().Append(m_titleText);
        m_appTitleBar.Children().Append(brandStack);

        StackPanel statusStack;
        statusStack.Margin(Microsoft::UI::Xaml::Thickness{ 0, 0, 140, 0 });
        statusStack.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Right);
        statusStack.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        statusStack.Orientation(Orientation::Horizontal);
        statusStack.Spacing(8);

        Button languageToggle;
        languageToggle.Width(56);
        languageToggle.Height(28);
        languageToggle.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ kCornerRadius });
        languageToggle.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        languageToggle.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        languageToggle.Background(ResourceBrush(L"AppControlBrush"));
        AutomationProperties::SetAutomationId(languageToggle, L"LanguageToggleButton");
        AutomationProperties::SetName(languageToggle, L"Language");
        m_languageText = MakeTextBlock(Text(L"language_button"), kSecondaryFontSize, ResourceBrush(L"AppTextBrush"));
        m_languageText.Width(56);
        m_languageText.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Center);
        m_languageText.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        m_languageText.TextAlignment(Microsoft::UI::Xaml::TextAlignment::Center);
        languageToggle.Content(m_languageText);
        languageToggle.Click([this](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&)
        {
            ToggleLanguage();
        });

        m_backendStatusDot = Microsoft::UI::Xaml::Shapes::Ellipse();
        m_backendStatusDot.Width(8);
        m_backendStatusDot.Height(8);
        m_backendStatusDot.Fill(ResourceBrush(L"AppDisabledTextBrush"));

        m_backendStatusText = MakeTextBlock(Text(L"stopped"), kSecondaryFontSize, ResourceBrush(L"AppSecondaryTextBrush"));
        m_backendStatusText.VerticalAlignment(Microsoft::UI::Xaml::VerticalAlignment::Center);
        m_backendStatusText.MaxWidth(132);

        statusStack.Children().Append(languageToggle);
        statusStack.Children().Append(m_backendStatusDot);
        statusStack.Children().Append(m_backendStatusText);
        Grid::SetColumn(statusStack, 2);
        m_appTitleBar.Children().Append(statusStack);

        m_contentPanel = StackPanel();
        m_contentPanel.Padding(Microsoft::UI::Xaml::Thickness{ kPagePaddingX, kPagePaddingY, kPagePaddingX, kPagePaddingY });
        m_contentPanel.Spacing(kContentSpacing);
        m_contentPanel.HorizontalAlignment(Microsoft::UI::Xaml::HorizontalAlignment::Stretch);

        ScrollViewer contentScroll;
        contentScroll.VerticalScrollBarVisibility(ScrollBarVisibility::Auto);
        contentScroll.HorizontalScrollBarVisibility(ScrollBarVisibility::Disabled);
        contentScroll.VerticalScrollMode(ScrollMode::Enabled);
        contentScroll.HorizontalScrollMode(ScrollMode::Disabled);
        contentScroll.ZoomMode(ZoomMode::Disabled);
        contentScroll.Content(m_contentPanel);
        Grid::SetRow(contentScroll, 1);

        appSurface.Children().Append(m_appTitleBar);
        appSurface.Children().Append(contentScroll);

        root.Children().Append(rail);
        root.Children().Append(appSurface);
        shell.Children().Append(root);
        Content(shell);
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: event handlers wired");
    }

    void MainWindow::ApplySystemBackdrop()
    {
        try
        {
            SystemBackdrop(MicaBackdrop());
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: MicaBackdrop applied");
        }
        catch (...)
        {
            SystemBackdrop(DesktopAcrylicBackdrop());
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: DesktopAcrylicBackdrop applied");
        }
    }

    void MainWindow::ToggleLanguage()
    {
        m_useChinese = !m_useChinese;
        UpdateShellText();
        NavigateTo(m_currentTag);
    }

    void MainWindow::UpdateShellText()
    {
        if (m_subtitleText)
        {
            m_subtitleText.Text(Text(L"brand_subtitle"));
        }
        if (m_languageText)
        {
            m_languageText.Text(Text(L"language_button"));
        }
        SetBackendStatus(
            m_cachedStatus.reachable ? (m_useChinese ? L"运行中" : L"Running") : Text(L"stopped"),
            m_cachedStatus.reachable);
    }

    void MainWindow::UpdateNavigationState()
    {
        for (uint32_t index = 0; index < m_navItems.size(); ++index)
        {
            auto item = m_navItems[index];
            bool selected = m_navTags[index] == m_currentTag;
            item.Background(ResourceBrush(selected ? L"AppSelectedBrush" : L"AppSurfaceBrush"));
            auto grid = item.Child().try_as<Grid>();
            if (!grid || grid.Children().Size() < 2)
            {
                continue;
            }
            if (auto indicator = grid.Children().GetAt(0).try_as<Microsoft::UI::Xaml::Shapes::Rectangle>())
            {
                indicator.Fill(selected ? ResourceBrush(L"AppAccentBrush") : ColorBrush(0, 0, 0, 0));
            }
            if (auto icon = grid.Children().GetAt(1).try_as<TextBlock>())
            {
                icon.Foreground(selected ? ResourceBrush(L"AppTextBrush") : ResourceBrush(L"AppSecondaryTextBrush"));
            }
        }
    }

    void MainWindow::StartLiveRefresh()
    {
        m_liveRefreshTimer = DispatcherQueue().CreateTimer();
        m_liveRefreshTimer.Interval(std::chrono::seconds(1));
        m_liveRefreshTimer.IsRepeating(true);
        m_liveRefreshTimer.Tick([this](Microsoft::UI::Dispatching::DispatcherQueueTimer const&, winrt::Windows::Foundation::IInspectable const&)
        {
            QueueBackendRefresh(m_currentTag);
        });
        m_liveRefreshTimer.Start();
        ::Gemini2API::WriteRuntimeLog(L"MainWindow: one-second live refresh timer started");
    }

    void MainWindow::StartBackendService()
    {
        m_currentTag = L"server";
        UpdateNavigationState();

        auto status = m_backendClient.GetStatus();
        if (status.reachable)
        {
            m_cachedStatus = status;
            SetBackendStatus(m_useChinese ? L"运行中" : L"Running", true);
            QueueBackendRefresh(L"server");
            return;
        }

        auto repoRoot = FindRepositoryRoot();
        if (repoRoot.empty())
        {
            SetBackendStatus(m_useChinese ? L"未找到仓库" : L"Repo not found", false);
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: backend start failed; repository root was not found");
            return;
        }

        auto configPath = BackendConfigPath(repoRoot);
        auto supervisorExe = FindSupervisorExecutable(repoRoot);
        bool started = m_backendProcess.Start(L"python", configPath, 18081, repoRoot, supervisorExe);
        if (!started)
        {
            SetBackendStatus(m_useChinese ? L"启动失败" : L"Start failed", false);
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: backend start failed; CreateProcessW returned false");
            return;
        }

        SetBackendStatus(m_useChinese ? L"启动中" : L"Starting", true);
        ::Gemini2API::WriteRuntimeLog(
            m_backendProcess.IsUsingSupervisor()
                ? L"MainWindow: backend process started through Rust supervisor"
                : L"MainWindow: backend process started through native fallback");
        QueueBackendRefresh(L"server");
    }

    void MainWindow::StopBackendService()
    {
        m_currentTag = L"server";
        UpdateNavigationState();

        if (m_backendProcess.IsRunning())
        {
            m_backendProcess.Stop();
            ::Gemini2API::WriteRuntimeLog(L"MainWindow: backend process stopped");
        }

        m_cachedStatus.reachable = false;
        m_cachedStatus.httpStatus = 0;
        m_cachedStatus.version.clear();
        SetBackendStatus(Text(L"stopped"), false);
        QueueBackendRefresh(L"server");
    }

    void MainWindow::OpenDashboard()
    {
        ShellExecuteW(nullptr, L"open", L"http://127.0.0.1:18081/dashboard", nullptr, nullptr, SW_SHOWNORMAL);
    }

    void MainWindow::RootNavigation_SelectionChanged(
        NavigationView const&,
        NavigationViewSelectionChangedEventArgs const& args)
    {
        auto selected = args.SelectedItem().try_as<NavigationViewItem>();
        if (!selected)
        {
            return;
        }

        auto tag = winrt::unbox_value_or<winrt::hstring>(selected.Tag(), L"");
        if (!tag.empty())
        {
            NavigateTo(tag);
        }
    }

    void MainWindow::QueueBackendRefresh(winrt::hstring const& tag)
    {
        if (m_backendRefreshInFlight.exchange(true))
        {
            return;
        }

        auto version = ++m_backendRefreshVersion;
        auto lifetime = get_strong();
        auto dispatcher = DispatcherQueue();
        std::thread([this, lifetime, dispatcher, tag, version]()
        {
            auto statsJson = m_backendClient.GetAdminStatsJson();
            auto status = m_backendClient.GetStatus();
            bool queued = dispatcher.TryEnqueue([this, lifetime, tag, version, statsJson = std::move(statsJson), status]() mutable
            {
                if (version < m_backendRefreshVersion.load())
                {
                    m_backendRefreshInFlight.store(false);
                    return;
                }

                m_cachedStatsJson = std::move(statsJson);
                m_cachedStatus = status;
                SetBackendStatus(
                    status.reachable ? (m_useChinese ? L"运行中" : L"Running") : Text(L"stopped"),
                    status.reachable);

                if (m_currentTag == tag)
                {
                    NavigateTo(tag, false);
                }
                m_backendRefreshInFlight.store(false);
            });
            if (!queued)
            {
                m_backendRefreshInFlight.store(false);
            }
        }).detach();
    }

    void MainWindow::NavigateTo(winrt::hstring const& tag, bool allowBackendRefresh)
    {
        ::Gemini2API::WriteRuntimeLog(std::wstring(L"MainWindow: NavigateTo ") + tag.c_str());
        if (!m_contentPanel)
        {
            return;
        }

        m_currentTag = tag;
        UpdateNavigationState();
        m_contentPanel.Children().Clear();

        auto stats = ParseJsonObject(H(m_cachedStatsJson));
        auto summary = GetJsonObject(stats, L"summary");

        auto percent = [](winrt::hstring const& value)
        {
            return H(std::wstring(value.c_str()) + L"%");
        };

        auto appendRowsPanel = [&](std::initializer_list<std::pair<winrt::hstring, winrt::hstring>> rows)
        {
            Border panel = MakeFlatPanel();
            StackPanel stack;
            stack.Spacing(2);
            for (auto const& row : rows)
            {
                AppendInfoRow(stack, row.first, row.second);
            }
            panel.Child(stack);
            m_contentPanel.Children().Append(panel);
        };

        if (tag == L"server")
        {
            auto status = m_cachedStatus;
            AppendPageHeader(m_contentPanel, Text(L"server_title"), Text(L"server_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"网络" : L"Network",
                m_useChinese ? L"进程" : L"Process",
                m_useChinese ? L"代理" : L"Proxy",
                m_useChinese ? L"启动" : L"Startup" });
            AppendMetricRow(
                m_contentPanel,
                Text(L"endpoint"),
                H(status.baseUrl),
                m_useChinese ? L"HTTP" : L"HTTP",
                status.httpStatus ? H(FormatNumber(status.httpStatus)) : winrt::hstring(L"--"),
                m_useChinese ? L"版本" : L"Version",
                status.version.empty() ? winrt::hstring(L"--") : H(status.version),
                m_useChinese ? L"状态" : L"Status",
                status.reachable ? (m_useChinese ? L"可达" : L"Reachable") : (m_useChinese ? L"等待后端" : L"Waiting"));

            auto startButton = MakeCommandButton(m_useChinese ? L"启动服务" : L"Start service", L"StartBackendButton");
            startButton.Click([this](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&)
            {
                StartBackendService();
            });
            auto stopButton = MakeCommandButton(m_useChinese ? L"停止服务" : L"Stop service", L"StopBackendButton");
            stopButton.Click([this](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&)
            {
                StopBackendService();
            });
            auto dashboardButton = MakeCommandButton(m_useChinese ? L"打开管理台" : L"Open dashboard", L"OpenDashboardButton");
            dashboardButton.Click([this](winrt::Windows::Foundation::IInspectable const&, Microsoft::UI::Xaml::RoutedEventArgs const&)
            {
                OpenDashboard();
            });
            AppendCommandRow(m_contentPanel, { startButton, stopButton, dashboardButton });

            appendRowsPanel({
                { Text(L"process_model"), Text(L"process_model_value") },
                { Text(L"refresh_cadence"), Text(L"refresh_cadence_value") },
                { m_useChinese ? L"托管进程" : L"Managed process",
                    m_backendProcess.IsRunning()
                        ? H(std::wstring(m_backendProcess.IsUsingSupervisor()
                            ? (m_useChinese ? L"Rust supervisor PID " : L"Rust supervisor PID ")
                            : (m_useChinese ? L"原生回退 PID " : L"Native fallback PID ")) +
                            FormatNumber(static_cast<double>(m_backendProcess.ProcessId())))
                        : (m_useChinese ? L"未由原生壳启动" : L"Not started by native shell") },
                { m_useChinese ? L"统计接口" : L"Stats endpoint", L"/admin/stats" },
                { m_useChinese ? L"真实数据源" : L"Real data source",
                    status.reachable
                        ? (m_useChinese ? L"WinHTTP 本地后端轮询" : L"WinHTTP local backend polling")
                        : (m_useChinese ? L"后端暂不可达" : L"Backend not reachable yet") } });
        }
        else if (tag == L"cookies")
        {
            AppendPageHeader(m_contentPanel, Text(L"cookies_title"), Text(L"cookies_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"手动导入" : L"Manual",
                m_useChinese ? L"Edge 插件" : L"Edge Extension",
                m_useChinese ? L"内部浏览器" : L"Internal Browser",
                m_useChinese ? L"账号环境" : L"Accounts" });
            AppendMetricRow(
                m_contentPanel,
                m_useChinese ? L"Cookie 方式" : L"Cookie methods",
                L"3",
                m_useChinese ? L"导入识别" : L"Import parser",
                m_useChinese ? L"网络文件 / 文本" : L"Network file / text",
                m_useChinese ? L"插件推送" : L"Extension push",
                L"/api/cookie/push",
                m_useChinese ? L"内部环境" : L"Internal browser",
                L"/api/cookie/browser-login");
            appendRowsPanel({
                { Text(L"manual_import"), Text(L"manual_import_value") },
                { Text(L"edge_extension"), Text(L"edge_extension_value") },
                { Text(L"internal_browser"), Text(L"internal_browser_value") },
                { m_useChinese ? L"联动状态" : L"Bridge status", m_useChinese ? L"与现有后端 Cookie API 对齐" : L"Aligned with existing backend cookie APIs" } });
        }
        else if (tag == L"streaming")
        {
            AppendPageHeader(m_contentPanel, Text(L"streaming_title"), Text(L"streaming_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"实时" : L"Live",
                m_useChinese ? L"请求" : L"Requests",
                m_useChinese ? L"正文" : L"Bodies",
                m_useChinese ? L"耗时" : L"Timing" });
            AppendMetricRow(
                m_contentPanel,
                m_useChinese ? L"每分钟请求" : L"Requests/min",
                JsonNumber(summary, L"requests_per_minute"),
                m_useChinese ? L"平均耗时" : L"Avg latency",
                H(std::wstring(JsonNumber(summary, L"avg_latency_ms", L"0", 1).c_str()) + L" ms"),
                m_useChinese ? L"最后请求" : L"Last request",
                JsonString(summary, L"last_request_at", L"--"),
                m_useChinese ? L"成功率" : L"Success rate",
                percent(JsonNumber(summary, L"success_rate", L"0", 1)));
            AppendRecentRequests(m_contentPanel, stats, m_useChinese);
            AppendBodyPreview(m_contentPanel, stats, m_useChinese);
        }
        else if (tag == L"models")
        {
            AppendPageHeader(m_contentPanel, Text(L"models_title"), Text(L"models_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"模型" : L"Models",
                m_useChinese ? L"Token" : L"Tokens",
                m_useChinese ? L"趋势" : L"Trends",
                m_useChinese ? L"总量" : L"Operations" });
            AppendMetricRow(
                m_contentPanel,
                m_useChinese ? L"总 Token" : L"Total tokens",
                JsonNumber(summary, L"total_tokens"),
                m_useChinese ? L"请求 Token" : L"Prompt tokens",
                JsonNumber(summary, L"total_prompt_tokens"),
                m_useChinese ? L"返回 Token" : L"Completion tokens",
                JsonNumber(summary, L"total_completion_tokens"),
                m_useChinese ? L"平均/请求" : L"Avg/request",
                JsonNumber(summary, L"avg_tokens_per_request", L"0", 1));
            appendRowsPanel({
                { Text(L"model_source"), Text(L"model_source_value") },
                { Text(L"token_metrics"), Text(L"token_metrics_value") },
                { Text(L"operations"), Text(L"operations_value") } });
            AppendModelUsageTable(m_contentPanel, stats, m_useChinese);
            AppendTrendPreview(m_contentPanel, stats, m_useChinese);
        }
        else if (tag == L"logs")
        {
            AppendPageHeader(m_contentPanel, Text(L"logs_title"), Text(L"logs_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"事件" : L"Events",
                m_useChinese ? L"代理" : L"Proxy",
                m_useChinese ? L"请求明细" : L"Request Details",
                m_useChinese ? L"保留" : L"Retention" });
            AppendMetricRow(
                m_contentPanel,
                m_useChinese ? L"总请求" : L"Total requests",
                JsonNumber(summary, L"total_requests"),
                m_useChinese ? L"错误" : L"Errors",
                JsonNumber(summary, L"total_errors"),
                m_useChinese ? L"成功率" : L"Success rate",
                percent(JsonNumber(summary, L"success_rate", L"0", 1)),
                m_useChinese ? L"每分钟请求" : L"Requests/min",
                JsonNumber(summary, L"requests_per_minute"));
            AppendRecentRequests(m_contentPanel, stats, m_useChinese);
            AppendBodyPreview(m_contentPanel, stats, m_useChinese);
            appendRowsPanel({
                { Text(L"proxy"), Text(L"proxy_value") },
                { Text(L"retention"), Text(L"retention_value") } });
        }
        else if (tag == L"settings")
        {
            AppendPageHeader(m_contentPanel, Text(L"settings_title"), Text(L"settings_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"语言" : L"Language",
                m_useChinese ? L"刷新" : L"Refresh",
                m_useChinese ? L"代理" : L"Proxy",
                m_useChinese ? L"视觉层" : L"Visual Layer" });
            AppendMetricRow(
                m_contentPanel,
                Text(L"language"),
                Text(L"language_value"),
                Text(L"refresh"),
                Text(L"refresh_value"),
                Text(L"proxy"),
                Text(L"proxy_settings_value"),
                Text(L"visual_layer"),
                Text(L"visual_layer_value"));
        }
        else
        {
            auto status = m_cachedStatus;
            AppendPageHeader(m_contentPanel, Text(L"overview_title"), Text(L"overview_subtitle"));
            AppendModeBar(m_contentPanel, {
                m_useChinese ? L"原生" : L"Native",
                m_useChinese ? L"后端" : L"Backend",
                m_useChinese ? L"运维" : L"Operations",
                m_useChinese ? L"视觉" : L"Visual" });
            AppendMetricRow(
                m_contentPanel,
                Text(L"runtime"),
                Text(L"runtime_value"),
                Text(L"backdrop"),
                Text(L"backdrop_value"),
                m_useChinese ? L"后端状态" : L"Backend status",
                status.reachable ? (m_useChinese ? L"可达" : L"Reachable") : (m_useChinese ? L"等待" : L"Waiting"),
                m_useChinese ? L"总请求" : L"Total requests",
                JsonNumber(summary, L"total_requests"));
            AppendTrendPreview(m_contentPanel, stats, m_useChinese);
        }
        if (allowBackendRefresh)
        {
            QueueBackendRefresh(tag);
        }
        ::Gemini2API::WriteRuntimeLog(std::wstring(L"MainWindow: NavigateTo complete ") + tag.c_str());
    }

    void MainWindow::SetBackendStatus(winrt::hstring const& text, bool running)
    {
        m_backendStatusText.Text(text);
        m_backendStatusDot.Fill(
            running
                ? ResourceBrush(L"AppAccentBrush")
                : ResourceBrush(L"AppDisabledTextBrush"));
    }
}
