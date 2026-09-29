# Generates the raw announcer voice lines with the Windows speech synthesizer.
# The game robotises them at first launch (see game/audio/synth.py:robotize).
# Usage:  powershell -ExecutionPolicy Bypass -File tools\gen_voice.ps1
param([string]$OutDir = "$PSScriptRoot\..\assets\voice")

Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$lines = [ordered]@{
    "fight"          = "Fight!"
    "first_blood"    = "First blood."
    "double_kill"    = "Double kill."
    "triple_kill"    = "Triple kill."
    "multi_kill"     = "Multi kill!"
    "killing_spree"  = "Killing spree."
    "rampage"        = "Rampage!"
    "unstoppable"    = "Unstoppable!"
    "headshot"       = "Headshot."
    "one_minute"     = "One minute remaining."
    "victory"        = "Victory."
    "defeat"         = "Defeat."
    "wave_incoming"  = "Wave incoming."
    "wave_cleared"   = "Wave cleared."
    "three"          = "Three."
    "two"            = "Two."
    "one"            = "One."
    "lead_taken"     = "You have taken the lead."
    "lead_lost"      = "You have lost the lead."
}

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
# Prefer a male voice if one is installed (sounds better robotised).
$male = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Gender -eq 'Male' -and $_.VoiceInfo.Culture.Name -like 'en*' } | Select-Object -First 1
if ($male) { $synth.SelectVoice($male.VoiceInfo.Name) }
$synth.Rate = -1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($k in $lines.Keys) {
    $path = Join-Path $OutDir "$k.wav"
    $synth.SetOutputToWaveFile($path, $fmt)
    $synth.Speak($lines[$k])
}
$synth.SetOutputToNull()
$synth.Dispose()
Write-Output "Generated $($lines.Count) voice lines in $OutDir"
