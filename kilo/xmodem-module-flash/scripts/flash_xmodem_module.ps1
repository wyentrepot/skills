param(
    [string]$FirmwarePath,
    [string]$Port,
    [int]$BaudRate = 115200,
    [ValidateSet("None", "Odd", "Even", "Mark", "Space")]
    [string]$Parity = "None",
    [int]$DataBits = 8,
    [ValidateSet("One", "OnePointFive", "Two")]
    [string]$StopBits = "One",
    [int]$ImageSlot = 0,
    [string]$LogDir,
    [switch]$ListPorts,
    [switch]$DryRun,
    [switch]$SelfTest,
    [switch]$NoRebootAfter,
    [string]$EnterBootloaderCommand = "reboot",
    [int]$PromptTimeoutMs = 3000,
    [int]$BootTimeoutMs = 12000,
    [int]$XmodemTimeoutMs = 30000,
    [int]$ResponseTimeoutMs = 10000
)

$ErrorActionPreference = "Stop"
$ACK = 0x06
$NAK = 0x15
$CAN = 0x18
$SOH = 0x01
$EOT = 0x04
$CRCCHR = 0x43
$PAD = 0x1A

function Get-SerialPorts {
    [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
}

function Show-SerialPorts {
    $ports = @(Get-SerialPorts)
    if ($ports.Count -eq 0) {
        Write-Host "No COM ports are visible."
        return
    }
    Write-Host "Visible COM ports:"
    foreach ($p in $ports) { Write-Host "  $p" }
}

function Select-SerialPort([string]$RequestedPort) {
    if (-not [string]::IsNullOrWhiteSpace($RequestedPort)) {
        return $RequestedPort.ToUpperInvariant()
    }

    Show-SerialPorts
    $selected = Read-Host "Select target COM port"
    if ([string]::IsNullOrWhiteSpace($selected)) {
        throw "No COM port selected."
    }
    return $selected.ToUpperInvariant()
}

function Resolve-FirmwareFile([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw "FirmwarePath is required."
    }

    if (Test-Path -LiteralPath $PathValue) {
        return (Resolve-Path -LiteralPath $PathValue).ProviderPath
    }

    if ($PathValue.StartsWith("/")) {
        $converted = (& wsl.exe -e wslpath -w -- "$PathValue" 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($converted) -and (Test-Path -LiteralPath $converted)) {
            return (Resolve-Path -LiteralPath $converted).ProviderPath
        }
    }

    throw "Firmware image not found: $PathValue"
}

function New-LogWriter([string]$Directory) {
    if ([string]::IsNullOrWhiteSpace($Directory)) {
        $Directory = Join-Path $env:TEMP "codex-module-flash"
    }
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $path = Join-Path $Directory "module-flash-$stamp.log"
    $writer = [System.IO.StreamWriter]::new($path, $false, [System.Text.Encoding]::UTF8)
    return [pscustomobject]@{ Path = $path; Writer = $writer }
}

function Write-Log([object]$Log, [string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss.fff"), $Message
    Write-Host $line
    if ($null -ne $Log) {
        $Log.Writer.WriteLine($line)
        $Log.Writer.Flush()
    }
}

function Convert-Text([byte[]]$Bytes, [int]$Count) {
    if ($Count -le 0) { return "" }
    return [System.Text.Encoding]::ASCII.GetString($Bytes, 0, $Count)
}

function Read-TextUntilQuiet($Serial, [int]$TimeoutMs, [int]$QuietMs, [object]$Log) {
    $buffer = New-Object byte[] 4096
    $sb = [System.Text.StringBuilder]::new()
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    $lastData = [DateTime]::UtcNow

    while ([DateTime]::UtcNow -lt $deadline) {
        $available = $Serial.BytesToRead
        if ($available -gt 0) {
            $count = $Serial.Read($buffer, 0, [Math]::Min($buffer.Length, $available))
            $text = Convert-Text $buffer $count
            [void]$sb.Append($text)
            $lastData = [DateTime]::UtcNow
        } elseif ((([DateTime]::UtcNow - $lastData).TotalMilliseconds -ge $QuietMs) -and $sb.Length -gt 0) {
            break
        } else {
            Start-Sleep -Milliseconds 25
        }
    }

    $result = $sb.ToString()
    if ($result.Length -gt 0) {
        Write-Log $Log ("RX text: " + ($result -replace "`r", "\\r" -replace "`n", "\\n"))
    }
    return $result
}

function Read-ByteWithTimeout($Serial, [int]$TimeoutMs) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Serial.BytesToRead -gt 0) {
            return $Serial.ReadByte()
        }
        Start-Sleep -Milliseconds 10
    }
    return -1
}

function Send-Line($Serial, [string]$Line, [object]$Log) {
    Write-Log $Log ("TX line: " + $Line)
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($Line + "`r`n")
    $Serial.Write($bytes, 0, $bytes.Length)
}

function Test-BootloaderText([string]$Text) {
    return ($Text -match "\[image /\]#")
}

function Invoke-BootloaderNavigation($Serial, [string]$Text, [object]$Log) {
    $extra = ""
    if ($Text -match "Press 'd' key") {
        Write-Log $Log "TX boot key: d"
        $bytes = [System.Text.Encoding]::ASCII.GetBytes("d")
        $Serial.Write($bytes, 0, $bytes.Length)
        $extra += Read-TextUntilQuiet $Serial 2000 200 $Log
    }
    if (($Text + $extra) -match "\[root /\]#") {
        Send-Line $Serial "image" $Log
        $extra += Read-TextUntilQuiet $Serial 2000 200 $Log
    }
    return ($Text + $extra)
}

function Wait-BootloaderPrompt($Serial, [object]$Log) {
    Send-Line $Serial "" $Log
    $text = Read-TextUntilQuiet $Serial $PromptTimeoutMs 200 $Log
    $text = Invoke-BootloaderNavigation $Serial $text $Log
    if (Test-BootloaderText $text) { return $true }

    if (-not [string]::IsNullOrWhiteSpace($EnterBootloaderCommand)) {
        Send-Line $Serial $EnterBootloaderCommand $Log
    }

    $deadline = [DateTime]::UtcNow.AddMilliseconds($BootTimeoutMs)
    $all = ""
    $ctrlC = [byte[]](0x03)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Serial.BytesToRead -eq 0) {
            $Serial.Write($ctrlC, 0, 1)
            Start-Sleep -Milliseconds 150
        }
        $chunk = Read-TextUntilQuiet $Serial 500 120 $Log
        if ($chunk.Length -gt 0) {
            $all += Invoke-BootloaderNavigation $Serial $chunk $Log
            if (Test-BootloaderText $all) { return $true }
        }
    }
    return $false
}

function Get-XmodemCrc16([byte[]]$Bytes, [int]$Offset, [int]$Count) {
    [int]$crc = 0
    for ($i = 0; $i -lt $Count; $i++) {
        $crc = $crc -bxor (($Bytes[$Offset + $i] -band 0xff) -shl 8)
        for ($bit = 0; $bit -lt 8; $bit++) {
            if (($crc -band 0x8000) -ne 0) {
                $crc = (($crc -shl 1) -bxor 0x1021) -band 0xffff
            } else {
                $crc = ($crc -shl 1) -band 0xffff
            }
        }
    }
    return ($crc -band 0xffff)
}

function New-XmodemPacket([byte[]]$Block, [int]$PacketNo, [bool]$UseCrc) {
    if ($Block.Length -ne 128) { throw "XMODEM block must be 128 bytes." }
    $tail = if ($UseCrc) { 2 } else { 1 }
    $packet = New-Object byte[] (3 + 128 + $tail)
    $seq = $PacketNo -band 0xff
    $packet[0] = [byte]$SOH
    $packet[1] = [byte]$seq
    $packet[2] = [byte](0xff - $seq)
    [Array]::Copy($Block, 0, $packet, 3, 128)
    if ($UseCrc) {
        $crc = Get-XmodemCrc16 $Block 0 128
        $packet[131] = [byte](($crc -shr 8) -band 0xff)
        $packet[132] = [byte]($crc -band 0xff)
    } else {
        [int]$sum = 0
        foreach ($b in $Block) { $sum = ($sum + $b) -band 0xff }
        $packet[131] = [byte]$sum
    }
    return $packet
}

function Wait-XmodemRequest($Serial, [object]$Log) {
    Write-Log $Log "Waiting for XMODEM receiver request."
    $deadline = [DateTime]::UtcNow.AddMilliseconds($XmodemTimeoutMs)
    while ([DateTime]::UtcNow -lt $deadline) {
        $b = Read-ByteWithTimeout $Serial 500
        if ($b -eq $CRCCHR) {
            Write-Log $Log "XMODEM mode: crc"
            return $true
        }
        if ($b -eq $NAK) {
            Write-Log $Log "XMODEM mode: checksum"
            return $false
        }
        if ($b -eq $CAN) {
            throw "Receiver cancelled XMODEM before transfer."
        }
    }
    throw "Timed out waiting for XMODEM request."
}

function Send-Xmodem($Serial, [byte[]]$ImageBytes, [bool]$UseCrc, [object]$Log) {
    $packetNo = 1
    $offset = 0
    $totalPackets = [Math]::Ceiling($ImageBytes.Length / 128.0)
    $lastProgress = -1

    while ($offset -lt $ImageBytes.Length) {
        $block = New-Object byte[] 128
        for ($i = 0; $i -lt 128; $i++) { $block[$i] = [byte]$PAD }
        $count = [Math]::Min(128, $ImageBytes.Length - $offset)
        [Array]::Copy($ImageBytes, $offset, $block, 0, $count)
        $packet = New-XmodemPacket $block $packetNo $UseCrc

        $sent = $false
        for ($retry = 0; $retry -lt 10 -and -not $sent; $retry++) {
            $Serial.Write($packet, 0, $packet.Length)
            $resp = Read-ByteWithTimeout $Serial $ResponseTimeoutMs
            if ($resp -eq $ACK) {
                $sent = $true
                $offset += $count
                $progress = [int][Math]::Floor(($offset * 100.0) / $ImageBytes.Length)
                if ($progress -ge ($lastProgress + 5) -or $offset -eq $ImageBytes.Length) {
                    $currentPacket = [Math]::Min($totalPackets, [Math]::Ceiling($offset / 128.0))
                    Write-Log $Log ("XMODEM progress packet={0}/{1} bytes={2}/{3} pct={4}" -f $currentPacket, $totalPackets, $offset, $ImageBytes.Length, $progress)
                    $lastProgress = $progress
                }
                $packetNo = ($packetNo + 1) -band 0xff
                if ($packetNo -eq 0) { $packetNo = 0 }
            } elseif ($resp -eq $NAK) {
                Write-Log $Log ("XMODEM retry packet=$packetNo attempt=$($retry + 1)")
            } elseif ($resp -eq $CAN) {
                throw "Receiver cancelled XMODEM transfer."
            } elseif ($resp -lt 0) {
                Write-Log $Log ("XMODEM timeout packet=$packetNo attempt=$($retry + 1)")
            } else {
                Write-Log $Log ("Unexpected XMODEM response 0x{0:X2} packet={1}" -f $resp, $packetNo)
            }
        }
        if (-not $sent) { throw "XMODEM packet $packetNo failed after retries." }
    }

    for ($retry = 0; $retry -lt 10; $retry++) {
        $Serial.Write([byte[]]($EOT), 0, 1)
        $resp = Read-ByteWithTimeout $Serial $ResponseTimeoutMs
        if ($resp -eq $ACK) {
            Write-Log $Log "XMODEM EOT ACK"
            return
        }
        if ($resp -eq $CAN) { throw "Receiver cancelled XMODEM at EOT." }
        Write-Log $Log ("Retry EOT, response={0}" -f $resp)
    }
    throw "XMODEM EOT was not acknowledged."
}

function Invoke-SelfTest {
    $bytes = [System.Text.Encoding]::ASCII.GetBytes("123456789")
    $crc = Get-XmodemCrc16 $bytes 0 $bytes.Length
    if ($crc -ne 0x31C3) { throw ("CRC self-test failed: 0x{0:X4}" -f $crc) }

    $block = New-Object byte[] 128
    for ($i = 0; $i -lt 128; $i++) { $block[$i] = [byte]$PAD }
    [Array]::Copy($bytes, 0, $block, 0, $bytes.Length)
    $packet = New-XmodemPacket $block 1 $true
    if ($packet.Length -ne 133) { throw "Packet length self-test failed." }
    if ($packet[0] -ne $SOH -or $packet[1] -ne 1 -or $packet[2] -ne 254) { throw "Packet header self-test failed." }
    Write-Host "Self-test PASS: CRC16/XMODEM and packet construction are valid."
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

if ($ListPorts) {
    Show-SerialPorts
    exit 0
}

$resolvedFirmware = Resolve-FirmwareFile $FirmwarePath
$selectedPort = Select-SerialPort $Port
$firmwareItem = Get-Item -LiteralPath $resolvedFirmware

if ($DryRun) {
    Write-Host "Dry-run PASS"
    Write-Host "  Firmware : $resolvedFirmware"
    Write-Host "  Size     : $($firmwareItem.Length) bytes"
    Write-Host "  Port     : $selectedPort"
    Write-Host "  Serial   : $BaudRate $DataBits$Parity $StopBits"
    Write-Host "  Command  : download $ImageSlot"
    exit 0
}

$imageBytes = [System.IO.File]::ReadAllBytes($resolvedFirmware)
$log = New-LogWriter $LogDir
$serial = $null
try {
    Write-Log $log ("Firmware: $resolvedFirmware size=$($imageBytes.Length)")
    Write-Log $log ("Opening $selectedPort at $BaudRate $DataBits$Parity $StopBits")
    $serial = [System.IO.Ports.SerialPort]::new($selectedPort, $BaudRate, [System.IO.Ports.Parity]::$Parity, $DataBits, [System.IO.Ports.StopBits]::$StopBits)
    $serial.ReadTimeout = 500
    $serial.WriteTimeout = 5000
    $serial.Open()

    if (-not (Wait-BootloaderPrompt $serial $log)) {
        throw "Bootloader prompt was not detected."
    }

    Send-Line $serial ("download $ImageSlot") $log
    $downloadText = Read-TextUntilQuiet $serial 5000 300 $log
    if ($downloadText -notmatch "overwrite|Press <Y>|continue|download") {
        Write-Log $log "Download prompt was not explicit; continuing cautiously."
    }

    Send-Line $serial "Y" $log
    [void](Read-TextUntilQuiet $serial 1500 300 $log)
    $useCrc = Wait-XmodemRequest $serial $log
    Send-Xmodem $serial $imageBytes $useCrc $log

    $resultText = Read-TextUntilQuiet $serial 12000 500 $log
    if ($resultText -notmatch "Image download OK|download .*success|success") {
        throw "XMODEM ended but bootloader success text was not observed. Log: $($log.Path)"
    }

    Write-Log $log "Image download confirmed."
    if (-not $NoRebootAfter) {
        Send-Line $serial "reboot" $log
        [void](Read-TextUntilQuiet $serial 3000 300 $log)
    }
    Write-Log $log "BURN SUCCESS"
    Write-Host "Log: $($log.Path)"
} finally {
    if ($null -ne $serial) {
        if ($serial.IsOpen) { $serial.Close() }
        $serial.Dispose()
    }
    if ($null -ne $log) {
        $log.Writer.Flush()
        $log.Writer.Dispose()
    }
}
