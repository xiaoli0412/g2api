#pragma once

#include "NativeLog.h"

namespace winrt::Gemini2API::Views
{
    inline Microsoft::UI::Xaml::Media::Brush ResourceBrush(wchar_t const* key)
    {
        auto brush = [](uint8_t a, uint8_t r, uint8_t g, uint8_t b)
        {
            return Microsoft::UI::Xaml::Media::SolidColorBrush(Windows::UI::Color{ a, r, g, b });
        };

        std::wstring_view name{ key };
        if (name == L"AppSurfaceBrush") return brush(235, 32, 32, 32);
        if (name == L"AppLayerBrush") return brush(242, 37, 37, 37);
        if (name == L"AppControlBrush") return brush(255, 43, 43, 43);
        if (name == L"AppHoverBrush") return brush(255, 45, 45, 45);
        if (name == L"AppSelectedBrush") return brush(255, 59, 59, 59);
        if (name == L"AppBorderBrush") return brush(255, 51, 51, 51);
        if (name == L"AppAccentBrush") return brush(255, 0, 120, 212);
        if (name == L"AppDangerBrush") return brush(255, 232, 17, 35);
        if (name == L"AppTextBrush") return brush(255, 255, 255, 255);
        if (name == L"AppSecondaryTextBrush") return brush(255, 153, 153, 153);
        if (name == L"AppDisabledTextBrush") return brush(255, 102, 102, 102);
        return brush(255, 255, 255, 255);
    }

    inline Microsoft::UI::Xaml::Controls::TextBlock Text(
        winrt::hstring const& value,
        double fontSize,
        Microsoft::UI::Xaml::Media::Brush const& foreground)
    {
        Microsoft::UI::Xaml::Controls::TextBlock block;
        block.Text(value);
        block.FontSize(fontSize);
        block.Foreground(foreground);
        block.TextWrapping(Microsoft::UI::Xaml::TextWrapping::Wrap);
        return block;
    }

    inline void AppendInfoRow(
        Microsoft::UI::Xaml::Controls::StackPanel const& panel,
        winrt::hstring const& label,
        winrt::hstring const& value)
    {
        Microsoft::UI::Xaml::Controls::Grid row;
        row.ColumnSpacing(16);
        row.Padding(Microsoft::UI::Xaml::Thickness{ 0, 6, 0, 6 });

        Microsoft::UI::Xaml::Controls::ColumnDefinition labelColumn;
        labelColumn.Width(Microsoft::UI::Xaml::GridLength{ 176, Microsoft::UI::Xaml::GridUnitType::Pixel });
        row.ColumnDefinitions().Append(labelColumn);

        Microsoft::UI::Xaml::Controls::ColumnDefinition valueColumn;
        valueColumn.Width(Microsoft::UI::Xaml::GridLength{ 1, Microsoft::UI::Xaml::GridUnitType::Star });
        row.ColumnDefinitions().Append(valueColumn);

        auto labelText = Text(label, 12, ResourceBrush(L"AppSecondaryTextBrush"));
        auto valueText = Text(value, 13, ResourceBrush(L"AppTextBrush"));
        Microsoft::UI::Xaml::Controls::Grid::SetColumn(valueText, 1);

        row.Children().Append(labelText);
        row.Children().Append(valueText);
        panel.Children().Append(row);
    }

    inline Microsoft::UI::Xaml::UIElement BuildPage(
        winrt::hstring const& title,
        winrt::hstring const& subtitle,
        winrt::hstring const& firstLabel,
        winrt::hstring const& firstValue,
        winrt::hstring const& secondLabel,
        winrt::hstring const& secondValue,
        winrt::hstring const& thirdLabel,
        winrt::hstring const& thirdValue)
    {
        ::Gemini2API::WriteRuntimeLog(std::wstring(L"PageContent: BuildPage ") + title.c_str());
        Microsoft::UI::Xaml::Controls::ScrollViewer viewer;
        viewer.VerticalScrollBarVisibility(Microsoft::UI::Xaml::Controls::ScrollBarVisibility::Auto);

        Microsoft::UI::Xaml::Controls::StackPanel root;
        root.Padding(Microsoft::UI::Xaml::Thickness{ 20, 16, 20, 16 });
        root.Spacing(16);

        auto titleText = Text(title, 14, ResourceBrush(L"AppTextBrush"));
        titleText.FontWeight(Microsoft::UI::Text::FontWeights::SemiBold());
        root.Children().Append(titleText);
        root.Children().Append(Text(subtitle, 12, ResourceBrush(L"AppSecondaryTextBrush")));

        Microsoft::UI::Xaml::Controls::Border panel;
        panel.Background(ResourceBrush(L"AppLayerBrush"));
        panel.BorderBrush(ResourceBrush(L"AppBorderBrush"));
        panel.BorderThickness(Microsoft::UI::Xaml::Thickness{ 1 });
        panel.CornerRadius(Microsoft::UI::Xaml::CornerRadius{ 4 });
        panel.Padding(Microsoft::UI::Xaml::Thickness{ 16 });

        Microsoft::UI::Xaml::Controls::StackPanel rows;
        rows.Spacing(2);
        AppendInfoRow(rows, firstLabel, firstValue);
        AppendInfoRow(rows, secondLabel, secondValue);
        AppendInfoRow(rows, thirdLabel, thirdValue);
        panel.Child(rows);

        root.Children().Append(panel);
        viewer.Content(root);
        return viewer;
    }
}
