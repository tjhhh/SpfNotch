param(
    [string]$Action = "status",
    [string]$Uri = ""
)

try {
    # If Action is play_uri, open Spotify with the URI and press Enter on the highlighted track
    if ($Action -and $Action.ToLower() -eq "play_uri" -and $Uri) {
        Start-Process $Uri
        Start-Sleep -Milliseconds 450

        try {
            $wshell = New-Object -ComObject WScript.Shell
            $proc = Get-Process -Name "Spotify" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | Select-Object -First 1
            if ($proc) {
                $wshell.AppActivate($proc.Id) | Out-Null
            } else {
                $wshell.AppActivate("Spotify") | Out-Null
            }
            Start-Sleep -Milliseconds 120
            $wshell.SendKeys("{ENTER}")
            Start-Sleep -Milliseconds 150
        } catch {
            # Continue
        }
    }

    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1

    function Await-WinRt($WinRtTask, $ResultType) {
        $netTask = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($WinRtTask))
        $netTask.Wait(2000) | Out-Null
        return $netTask.Result
    }

    [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime] | Out-Null
    $async = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
    $manager = Await-WinRt $async ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
    
    $sessions = $manager.GetSessions()
    $bestSession = $null

    # 1. Prefer Spotify session
    foreach ($s in $sessions) {
        $appId = ("" + $s.SourceAppId).ToLower()
        if ($appId -match "spotify") {
            $bestSession = $s
            break
        }
    }

    # 2. If no explicit spotify in AppId, check sessions that have media properties
    if (-not $bestSession) {
        foreach ($s in $sessions) {
            $propAsync = $s.TryGetMediaPropertiesAsync()
            $props = Await-WinRt $propAsync ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
            if ($props -and $props.Title) {
                $bestSession = $s
                break
            }
        }
    }

    if ($bestSession) {
        # Execute transport action if requested
        if ($Action -and $Action -ne "status" -and $Action -ne "play_uri") {
            switch ($Action.ToLower()) {
                "play" {
                    $actTask = $bestSession.TryPlayAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
                "pause" {
                    $actTask = $bestSession.TryPauseAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
                "toggle" {
                    $actTask = $bestSession.TryTogglePlayPauseAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
                "play_pause" {
                    $actTask = $bestSession.TryTogglePlayPauseAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
                "next" {
                    $actTask = $bestSession.TrySkipNextAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
                "prev" {
                    $actTask = $bestSession.TrySkipPreviousAsync()
                    Await-WinRt $actTask ([bool]) | Out-Null
                }
            }
            Start-Sleep -Milliseconds 80
        }

        $playbackInfo = $bestSession.GetPlaybackInfo()
        $propAsync = $bestSession.TryGetMediaPropertiesAsync()
        $props = Await-WinRt $propAsync ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])

        $statusStr = "Paused"
        if ($playbackInfo -and $playbackInfo.PlaybackStatus -eq [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionPlaybackStatus]::Playing) {
            $statusStr = "Playing"
        }

        $timeline = $bestSession.GetTimelineProperties()
        $posMs = 0
        $durMs = 0
        if ($timeline) {
            if ($timeline.Position) {
                $posMs = [int][Math]::Round($timeline.Position.TotalMilliseconds)
            }
            if ($timeline.EndTime) {
                $durMs = [int][Math]::Round($timeline.EndTime.TotalMilliseconds)
            }
        }

        [PSCustomObject]@{
            AppId = $bestSession.SourceAppId
            Status = $statusStr
            Title = $props.Title
            Artist = $props.Artist
            Album = $props.AlbumTitle
            PositionMs = $posMs
            DurationMs = $durMs
        } | ConvertTo-Json -Compress
    }
} catch {
    # Quiet error
}
