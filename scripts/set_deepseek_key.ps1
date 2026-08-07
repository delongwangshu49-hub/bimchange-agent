$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repositoryRoot ".env.local"
$secureKey = Read-Host "Paste a NEW DeepSeek API key (input is hidden)" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    if (-not $plainKey.StartsWith("sk-") -or $plainKey.Length -lt 20) {
        throw "The value does not look like a DeepSeek API key. Nothing was written."
    }

    $utf8WithoutBom = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText(
        $envPath,
        "DEEPSEEK_API_KEY=$plainKey`n",
        $utf8WithoutBom
    )
    Write-Host "Saved DEEPSEEK_API_KEY to the Git-ignored .env.local file."
}
finally {
    if ($keyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
    $plainKey = $null
    $secureKey = $null
}
