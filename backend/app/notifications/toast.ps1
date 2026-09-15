param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>SignalRadar</text><text></text><text></text></binding></visual></toast>')
    $nodes = $xml.GetElementsByTagName('text')
    $nodes.Item(1).AppendChild($xml.CreateTextNode([string]$payload.topic)) | Out-Null
    $nodes.Item(2).AppendChild($xml.CreateTextNode(('{0} new relevant items. A new Digest is ready.' -f [int]$payload.count))) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    # Existing Windows PowerShell app identity: no registry/shortcut registration needed.
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
    if ($ValidateOnly) { Write-Output 'Windows toast payload and notifier validated; no notification sent.'; exit 0 }
    $notifier.Show($toast)
} catch {
    [Console]::Error.WriteLine('Windows notification failed.')
    exit 1
}
