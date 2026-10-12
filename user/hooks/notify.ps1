param(
    [string]$Title = "Claude Code",
    [string]$Message = ""
)
# トースト通知と音で知らせる。hooks の notify.py から呼ばれる。失敗しても何もしない。
try {
    [System.Media.SystemSounds]::Asterisk.Play()
    $null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    $null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
    $t = [System.Security.SecurityElement]::Escape($Title)
    $m = [System.Security.SecurityElement]::Escape($Message)
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast><visual><binding template=`"ToastText02`"><text id=`"1`">$t</text><text id=`"2`">$m</text></binding></visual></toast>")
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    # Windows PowerShell の AppUserModelID。未登録の ID だとトーストが表示されない
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
    Start-Sleep -Seconds 1  # 音が鳴り終わる前にプロセスが終わらないようにする
} catch {
}
