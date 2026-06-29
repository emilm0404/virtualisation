using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Threading;
using Avalonia.Themes.Fluent;
using Avalonia.Markup.Xaml;
using Avalonia.Controls.Shapes;

namespace HyperXVisualizer;

class App : Application
{
    public override void Initialize()
    {
        Styles.Add(new FluentTheme());
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is Avalonia.Controls.ApplicationLifetimes.IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new MainWindow();
        }
        base.OnFrameworkInitializationCompleted();
    }
}

class MainWindow : Window
{
    private double _angle = 0;
    private DispatcherTimer _animationTimer;
    private Polygon _triangle;
    private TextBlock _ripLabel;
    private TextBlock _rspLabel;
    private TextBlock _logsBox;
    private TextBlock _statusText;
    private TextBox _vmNameInput;
    private TextBox _ramSizeInput;
    
    private Process _vmProcess;

    public MainWindow()
    {
        Title = "Hyper X Manager - GPU Virtualization Visualizer";
        Width = 1100;
        Height = 750;
        Background = SolidColorBrush.Parse("#1c1d22");
        
        var mainGrid = new Grid();
        mainGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("1*")));
        mainGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("1.2*")));
        mainGrid.Margin = new Thickness(20);
        
        var leftPanel = new StackPanel { Margin = new Thickness(0, 0, 10, 0) };
        Grid.SetColumn(leftPanel, 0);
        mainGrid.Children.Add(leftPanel);
        
        var statusCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15, 10, 15, 10),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var statusLayout = new DockPanel();
        var vmLabel = new TextBlock
        {
            Text = "Hyper X Manager Console",
            FontSize = 16,
            FontWeight = FontWeight.Bold,
            Foreground = Brushes.White,
            VerticalAlignment = VerticalAlignment.Center
        };
        _statusText = new TextBlock
        {
            Text = "● Stopped",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            VerticalAlignment = VerticalAlignment.Center
        };
        DockPanel.SetDock(vmLabel, Dock.Left);
        DockPanel.SetDock(_statusText, Dock.Right);
        statusLayout.Children.Add(vmLabel);
        statusLayout.Children.Add(_statusText);
        statusCard.Child = statusLayout;
        leftPanel.Children.Add(statusCard);

        var configCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var configLayout = new StackPanel();
        
        var configTitle = new TextBlock
        {
            Text = "VM CONFIGURATION PARAMETERS",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            Margin = new Thickness(0, 0, 0, 10)
        };
        configLayout.Children.Add(configTitle);

        var nameGrid = new Grid { Margin = new Thickness(0, 0, 0, 8) };
        nameGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("80")));
        nameGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("1*")));
        var nameLbl = new TextBlock { Text = "VM Name:", Foreground = Brushes.White, VerticalAlignment = VerticalAlignment.Center };
        _vmNameInput = new TextBox { Text = "hyperx-guest-vm", Background = SolidColorBrush.Parse("#1c1d22"), Foreground = Brushes.White, BorderBrush = SolidColorBrush.Parse("#313238") };
        Grid.SetColumn(nameLbl, 0);
        Grid.SetColumn(_vmNameInput, 1);
        nameGrid.Children.Add(nameLbl);
        nameGrid.Children.Add(_vmNameInput);
        configLayout.Children.Add(nameGrid);

        var ramGrid = new Grid { Margin = new Thickness(0, 0, 0, 15) };
        ramGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("80")));
        ramGrid.ColumnDefinitions.Add(new ColumnDefinition(GridLength.Parse("1*")));
        var ramLbl = new TextBlock { Text = "RAM (MB):", Foreground = Brushes.White, VerticalAlignment = VerticalAlignment.Center };
        _ramSizeInput = new TextBox { Text = "128", Background = SolidColorBrush.Parse("#1c1d22"), Foreground = Brushes.White, BorderBrush = SolidColorBrush.Parse("#313238") };
        Grid.SetColumn(ramLbl, 0);
        Grid.SetColumn(_ramSizeInput, 1);
        ramGrid.Children.Add(ramLbl);
        ramGrid.Children.Add(_ramSizeInput);
        configLayout.Children.Add(ramGrid);

        var actionsLayout = new UniformGrid { Columns = 2 };
        var startBtn = new Button
        {
            Content = "Start Virtual Machine",
            Background = SolidColorBrush.Parse("#9d4edd"),
            Foreground = Brushes.White,
            FontWeight = FontWeight.Bold,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(0, 0, 5, 0),
            Padding = new Thickness(10)
        };
        startBtn.Click += (s, e) => StartVM();

        var stopBtn = new Button
        {
            Content = "Stop Virtual Machine",
            Background = SolidColorBrush.Parse("#444"),
            Foreground = Brushes.White,
            FontWeight = FontWeight.Bold,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(5, 0, 0, 0),
            Padding = new Thickness(10)
        };
        stopBtn.Click += (s, e) => StopVM();

        actionsLayout.Children.Add(startBtn);
        actionsLayout.Children.Add(stopBtn);
        configLayout.Children.Add(actionsLayout);
        configCard.Child = configLayout;
        leftPanel.Children.Add(configCard);
        
        var vramCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var vramLayout = new StackPanel();
        var vramTitle = new TextBlock
        {
            Text = "SHARED VRAM LAYOUT (256MB)",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            Margin = new Thickness(0, 0, 0, 10)
        };
        vramLayout.Children.Add(vramTitle);
        
        var vramGrid = new UniformGrid { Columns = 8, Rows = 8, Margin = new Thickness(0, 0, 0, 10) };
        for (int i = 0; i < 64; i++)
        {
            var color = "#2c2d35";
            if (i < 4) color = "#00bbf9";
            else if (i >= 8 && i < 24) color = "#9d4edd";
            else if (i >= 32 && i < 48) color = "#00f5d4";
            
            vramGrid.Children.Add(new Border
            {
                Width = 28,
                Height = 28,
                Background = SolidColorBrush.Parse(color),
                Margin = new Thickness(2),
                CornerRadius = new CornerRadius(3)
            });
        }
        vramLayout.Children.Add(vramGrid);
        vramCard.Child = vramLayout;
        leftPanel.Children.Add(vramCard);
        
        var regsCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var regsLayout = new StackPanel();
        var regsTitle = new TextBlock
        {
            Text = "VIRTUAL PROCESSOR REGISTERS",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            Margin = new Thickness(0, 0, 0, 10)
        };
        regsLayout.Children.Add(regsTitle);
        
        var regsGrid = new UniformGrid { Columns = 2, Rows = 3 };
        _ripLabel = CreateRegisterBox("RIP", "0x00000000", regsGrid);
        _rspLabel = CreateRegisterBox("RSP", "0x00000000", regsGrid);
        CreateRegisterBox("RSI", "0x00000000", regsGrid);
        CreateRegisterBox("CR0", "0x00000000", regsGrid);
        CreateRegisterBox("CS", "0x0000", regsGrid);
        CreateRegisterBox("DS", "0x0000", regsGrid);
        
        regsLayout.Children.Add(regsGrid);
        regsCard.Child = regsLayout;
        leftPanel.Children.Add(regsCard);
        
        var rightPanel = new StackPanel { Margin = new Thickness(10, 0, 0, 0) };
        Grid.SetColumn(rightPanel, 1);
        mainGrid.Children.Add(rightPanel);
        
        var canvasCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var canvasLayout = new StackPanel();
        var canvasTitle = new TextBlock
        {
            Text = "HOST RENDERING CANVAS (X-GPU)",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            Margin = new Thickness(0, 0, 0, 10)
        };
        canvasLayout.Children.Add(canvasTitle);
        
        var canvasWrapper = new Canvas
        {
            Width = 400,
            Height = 300,
            Background = Brushes.Black,
            ClipToBounds = true
        };
        
        _triangle = new Polygon
        {
            Fill = SolidColorBrush.Parse("#444"),
            Stroke = SolidColorBrush.Parse("#666"),
            StrokeThickness = 2
        };
        canvasWrapper.Children.Add(_triangle);
        canvasLayout.Children.Add(canvasWrapper);
        canvasCard.Child = canvasLayout;
        rightPanel.Children.Add(canvasCard);
        
        var logsCard = new Border
        {
            Background = SolidColorBrush.Parse("#25262c"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(15),
            Margin = new Thickness(0, 0, 0, 15)
        };
        var logsLayout = new StackPanel();
        var logsTitle = new TextBlock
        {
            Text = "HYPERVISOR DOORBELL EXITS",
            FontSize = 12,
            FontWeight = FontWeight.Bold,
            Foreground = SolidColorBrush.Parse("#adb5bd"),
            Margin = new Thickness(0, 0, 0, 10)
        };
        logsLayout.Children.Add(logsTitle);
        
        var logsScroll = new ScrollViewer { Height = 180 };
        _logsBox = new TextBlock
        {
            Text = "Hyper X Manager console initialized. Press 'Start Virtual Machine' to execute.\n",
            FontFamily = new FontFamily("Courier New"),
            FontSize = 11,
            Foreground = Brushes.White,
            TextWrapping = TextWrapping.Wrap
        };
        logsScroll.Content = _logsBox;
        logsLayout.Children.Add(logsScroll);
        logsCard.Child = logsLayout;
        rightPanel.Children.Add(logsCard);
        
        Content = mainGrid;

        _animationTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(30)
        };
        _animationTimer.Tick += (s, e) => UpdateTriangleAnimation();
    }

    private TextBlock CreateRegisterBox(string name, string val, Panel container)
    {
        var box = new Border
        {
            Background = SolidColorBrush.Parse("#1c1d22"),
            BorderBrush = SolidColorBrush.Parse("#313238"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(4),
            Padding = new Thickness(8, 4, 8, 4),
            Margin = new Thickness(3)
        };
        var layout = new DockPanel();
        var nLbl = new TextBlock { Text = name, Foreground = SolidColorBrush.Parse("#c77dff"), FontWeight = FontWeight.Bold, FontSize = 11 };
        var vLbl = new TextBlock { Text = val, Foreground = Brushes.White, FontSize = 11 };
        DockPanel.SetDock(nLbl, Dock.Left);
        DockPanel.SetDock(vLbl, Dock.Right);
        layout.Children.Add(nLbl);
        layout.Children.Add(vLbl);
        box.Child = layout;
        container.Children.Add(box);
        return vLbl;
    }

    private void UpdateTriangleAnimation()
    {
        double cx = 200, cy = 150;
        double r = 80;
        
        var points = new List<Point>();
        for (int i = 0; i < 3; i++)
        {
            double theta = _angle + (i * 2 * Math.PI / 3);
            points.Add(new Point(cx + r * Math.Cos(theta), cy + r * Math.Sin(theta)));
        }
        
        _triangle.Points = points;
        _angle += 0.04;
    }

    private void StartVM()
    {
        if (_vmProcess != null && !_vmProcess.HasExited) return;

        _logsBox.Text = $"Booting {_vmNameInput.Text} with {_ramSizeInput.Text}MB allocated RAM...\n";
        _statusText.Text = "● Starting...";
        _statusText.Foreground = SolidColorBrush.Parse("#fee440");
        
        _triangle.Fill = SolidColorBrush.Parse("#9d4edd");
        _triangle.Stroke = SolidColorBrush.Parse("#00f5d4");
        _animationTimer.Start();

        var pythonExe = @"C:\Users\Emil\AppData\Local\Microsoft\WindowsApps\python3.13.exe";
        if (!File.Exists(pythonExe))
        {
            pythonExe = "python";
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = "example3.py",
            WorkingDirectory = @"C:\Users\Emil\Desktop\virtualsied machines",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        _vmProcess = new Process { StartInfo = startInfo };
        _vmProcess.OutputDataReceived += (sender, args) =>
        {
            if (args.Data != null)
            {
                Dispatcher.UIThread.Post(() =>
                {
                    _logsBox.Text += args.Data + "\n";
                    if (args.Data.Contains("running virtual processor"))
                    {
                        _statusText.Text = $"● Active ({_vmNameInput.Text})";
                        _statusText.Foreground = SolidColorBrush.Parse("#00f5d4");
                    }
                    var r = new Random();
                    _ripLabel.Text = $"0x00{0x100000 + r.Next(0xFFFF):X8}";
                    _rspLabel.Text = $"0x0000{0x7F00 + r.Next(256):X4}";
                });
            }
        };

        _vmProcess.ErrorDataReceived += (sender, args) =>
        {
            if (args.Data != null)
            {
                Dispatcher.UIThread.Post(() =>
                {
                    _logsBox.Text += "[error] " + args.Data + "\n";
                });
            }
        };

        try
        {
            _vmProcess.Start();
            _vmProcess.BeginOutputReadLine();
            _vmProcess.BeginErrorReadLine();
        }
        catch (Exception ex)
        {
            _logsBox.Text += $"Failed to start python execution script: {ex.Message}\n";
            _statusText.Text = "● Faulted";
            _statusText.Foreground = Brushes.Red;
        }
    }

    private void StopVM()
    {
        if (_vmProcess != null && !_vmProcess.HasExited)
        {
            try
            {
                _vmProcess.Kill(true);
            }
            catch {}
            _logsBox.Text += "Virtual Machine execution halted.\n";
        }
        _statusText.Text = "● Stopped";
        _statusText.Foreground = SolidColorBrush.Parse("#adb5bd");
        _triangle.Fill = SolidColorBrush.Parse("#444");
        _triangle.Stroke = SolidColorBrush.Parse("#666");
        _animationTimer.Stop();
    }

    protected override void OnClosed(EventArgs e)
    {
        StopVM();
        base.OnClosed(e);
    }
}

class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .LogToTrace()
            .StartWithClassicDesktopLifetime(args);
    }
}
