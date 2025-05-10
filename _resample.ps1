Get-ChildItem "data/raw/" -Recurse -File | ForEach-Object {
    $temp = Join-Path $_.DirectoryName "$($_.BaseName)_44100$($_.Extension)"
    ffmpeg -y -i "$($_.FullName)" -ar 44100 "$temp"
    Move-Item -Force $temp "$($_.FullName)"
}