Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$DevSecret = "",
  [Int64]$UserAKakaoId = 0,
  [Int64]$UserBKakaoId = 0,
  [int]$RestaurantId = 0,
  [string]$Pin = "",
  [switch]$RunSeed,
  [int]$FlashQuota = 0,
  [switch]$DoFlash,
  [switch]$DoStamps,
  [switch]$DoRedeem,
  [switch]$JsonOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:QUIET = $JsonOutput

function Write-Step($msg) { if (-not $script:QUIET) { Write-Host "[STEP] $msg" -ForegroundColor Cyan } }
function Write-Info($msg) { if (-not $script:QUIET) { Write-Host "[INFO] $msg" -ForegroundColor DarkGray } }
function Write-Ok($msg)   { if (-not $script:QUIET) { Write-Host "[OK]  $msg" -ForegroundColor Green } }
function Write-Warn($msg) { if (-not $script:QUIET) { Write-Host "[WARN] $msg" -ForegroundColor Yellow } }
function Write-Err($msg)  { if (-not $script:QUIET) { Write-Host "[ERR] $msg" -ForegroundColor Red } }

function Read-FromEnvFile {
  Param([Parameter(Mandatory=$true)][string]$Key)
  try {
    if (Test-Path -LiteralPath ".env") {
      $pattern = "^$([Regex]::Escape($Key))\s*=\s*(.+)$"
      $line = Select-String -Path .env -Pattern $pattern | Select-Object -First 1
      if ($null -ne $line) {
        $val = $line.Matches.Groups[1].Value.Trim()
        if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Trim('"') }
        if ($val.StartsWith("'") -and $val.EndsWith("'")) { $val = $val.Trim("'") }
        return $val
      }
    }
  } catch {}
  return $null
}

function Invoke-Json {
  Param(
    [Parameter(Mandatory=$true)][ValidateSet('GET','POST','PUT','PATCH','DELETE')] [string]$Method,
    [Parameter(Mandatory=$true)] [string]$Url,
    [hashtable]$Headers,
    $Body
  )
  $args = @{ Method = $Method; Uri = $Url }
  if ($null -ne $Headers) { $args.Headers = $Headers }
  if ($null -ne $Body) {
    $args.ContentType = 'application/json'
    $args.Body = ($Body | ConvertTo-Json -Depth 10)
  }
  try {
    return Invoke-RestMethod @args -ErrorAction Stop
  } catch {
    if ($_.Exception.Response) {
      try {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $text = $reader.ReadToEnd()
        Write-Err "HTTP error body: $text"
      } catch {}
    }
    throw
  }
}

function Dev-Login {
  Param([Int64]$KakaoId)
  $url = "$BaseUrl/auth/dev-login/"
  $headers = @{ 'X-Dev-Login-Secret' = $DevSecret }
  $body = @{ kakao_id = $KakaoId }
  return Invoke-Json -Method POST -Url $url -Headers $headers -Body $body
}

# Resolve defaults from .env/env if not provided
if (-not $DevSecret) { $DevSecret = (Read-FromEnvFile -Key 'DEV_LOGIN_SECRET') }
if (-not $DevSecret) { $DevSecret = $env:DEV_LOGIN_SECRET }
if (-not $DevSecret) { Write-Err "DEV_LOGIN_SECRET not provided. Pass -DevSecret or set in .env or ENV."; if (-not $JsonOutput) { exit 1 } }

if (-not $UserAKakaoId -or $UserAKakaoId -eq 0) {
  $val = (Read-FromEnvFile -Key 'DEV_USER_A_KAKAO_ID'); if (-not $val) { $val = $env:DEV_USER_A_KAKAO_ID }
  if ($val) { [Int64]$UserAKakaoId = $val } else { $UserAKakaoId = 900001 }
}
if (-not $UserBKakaoId -or $UserBKakaoId -eq 0) {
  $val = (Read-FromEnvFile -Key 'DEV_USER_B_KAKAO_ID'); if (-not $val) { $val = $env:DEV_USER_B_KAKAO_ID }
  if ($val) { [Int64]$UserBKakaoId = $val } else { $UserBKakaoId = 900002 }
}
if (-not $RestaurantId -or $RestaurantId -eq 0) {
  $val = (Read-FromEnvFile -Key 'DEV_RESTAURANT_ID'); if (-not $val) { $val = $env:DEV_RESTAURANT_ID }
  if ($val) { [int]$RestaurantId = $val } else { $RestaurantId = 1 }
}
if (-not $Pin) {
  $val = (Read-FromEnvFile -Key 'DEV_MERCHANT_PIN'); if (-not $val) { $val = $env:DEV_MERCHANT_PIN }
  if ($val) { $Pin = $val } else { $Pin = '1234' }
}

$summary = [ordered]@{
  base_url = $BaseUrl;
  userA = [ordered]@{ kakao_id = $UserAKakaoId };
  userB = [ordered]@{ kakao_id = $UserBKakaoId };
  referral = @{};
  signup = @{};
  flash = @{};
  stamp = @{};
  redeem = @{};
}

# Optional seeding
if ($RunSeed) {
  Write-Step "Seeding dev data (coupon types, campaigns, merchant pin)"
  $cmd = @('python','manage.py','seed_dev_coupons','--restaurant',$RestaurantId,'--pin',$Pin)
  if ($FlashQuota -gt 0) { $cmd += @('--flash-quota',"$FlashQuota") }
  try {
    & $cmd 2>&1 | ForEach-Object { Write-Info $_ }
    Write-Ok "Seeding completed"
  } catch {
    Write-Warn "Seeding failed. Ensure Python and dependencies are installed. Error: $($_.Exception.Message)"
  }
}

Write-Step "Dev login for User A ($UserAKakaoId)"
try {
  $loginA = Dev-Login -KakaoId $UserAKakaoId
  $accessA = $loginA.token.access
  $refreshA = $loginA.token.refresh
  $authA = @{ Authorization = "Bearer $accessA" }
  $summary.userA.access = $accessA; $summary.userA.refresh = $refreshA
  Write-Ok "User A access token obtained"
} catch {
  $summary.userA.error = $_.Exception.Message
  if ($JsonOutput) { $summary | ConvertTo-Json -Depth 8; exit 1 } else { throw }
}

Write-Step "Dev login for User B ($UserBKakaoId)"
try {
  $loginB = Dev-Login -KakaoId $UserBKakaoId
  $accessB = $loginB.token.access
  $refreshB = $loginB.token.refresh
  $authB = @{ Authorization = "Bearer $accessB" }
  $summary.userB.access = $accessB; $summary.userB.refresh = $refreshB
  Write-Ok "User B access token obtained"
} catch {
  $summary.userB.error = $_.Exception.Message
  if ($JsonOutput) { $summary | ConvertTo-Json -Depth 8; exit 1 } else { throw }
}

# Invite code for A
Write-Step "Ensure and fetch invite code for User A"
try {
  $invite = Invoke-Json -Method GET -Url "$BaseUrl/api/coupons/invite/my/" -Headers $authA
  $refCode = $invite.code
  $summary.userA.invite_code = $refCode
  Write-Ok "Invite code: $refCode"
} catch {
  $summary.referral.error = "invite_code: $($_.Exception.Message)"
  if ($JsonOutput) { $summary | ConvertTo-Json -Depth 8; exit 1 } else { throw }
}

# B accepts referral
Write-Step "User B accepts referral"
try {
  $acc = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/referrals/accept/" -Headers $authB -Body @{ ref_code = $refCode }
  Write-Ok "Referral accepted"
} catch {
  $summary.referral.error = "accept: $($_.Exception.Message)"
}

# B qualifies referral
Write-Step "Qualify referral for User B"
try {
  $qual = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/referrals/qualify/" -Headers $authB -Body @{}
  $summary.referral.status = $qual.status
  Write-Ok ("Referral status: " + ($qual.status | Out-String).Trim())
} catch {
  $summary.referral.error = "qualify: $($_.Exception.Message)"
}

# Signup welcome coupon for B
Write-Step "Issue signup coupon for User B"
$signup = $null
try {
  $signup = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/signup/complete/" -Headers $authB -Body @{}
  $summary.signup.coupon_code = $signup.coupon_code
  if ($signup.coupon_code) { Write-Ok "Signup coupon issued: $($signup.coupon_code)" } else { Write-Info "Signup: $($signup | ConvertTo-Json -Depth 5)" }
} catch {
  $summary.signup.error = $_.Exception.Message
  Write-Warn "Signup coupon request failed (may already exist): $($_.Exception.Message)"
}

# Optional: Flash claim for B
$flashCode = $null
if ($DoFlash) {
  Write-Step "Flash claim for User B"
  $idem = [guid]::NewGuid().ToString()
  $headersFlash = $authB.Clone()
  $headersFlash['Idempotency-Key'] = $idem
  try {
    $flash = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/flash/claim/" -Headers $headersFlash -Body @{}
    $flashCode = $flash.coupon_code
    $summary.flash.coupon_code = $flashCode
    Write-Ok "Flash coupon issued: $flashCode"
  } catch {
    $summary.flash.error = $_.Exception.Message
    Write-Warn "Flash claim failed (campaign/quota?): $($_.Exception.Message)"
  }
}

# Optional: Stamps for B
if ($DoStamps) {
  Write-Step "Add stamp for User B"
  $headersStamp = $authB.Clone(); $headersStamp['Idempotency-Key'] = ([guid]::NewGuid().ToString())
  try {
    $stamp = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/stamps/add/" -Headers $headersStamp -Body @{ restaurant_id = $RestaurantId; pin = $Pin }
    $summary.stamp.add = $stamp
    Write-Ok ("Stamp result: " + ($stamp | ConvertTo-Json -Depth 5))
  } catch {
    $summary.stamp.error = "add: $($_.Exception.Message)"
    Write-Warn "Stamp add failed (check MerchantPin): $($_.Exception.Message)"
  }
  try {
    $status = Invoke-Json -Method GET -Url "$BaseUrl/api/coupons/stamps/my/?restaurant_id=$RestaurantId" -Headers $authB -Body $null
    $summary.stamp.status = $status
    Write-Ok ("Stamp status: " + ($status | ConvertTo-Json -Depth 5))
  } catch {
    $summary.stamp.error = "status: $($_.Exception.Message)"
    Write-Warn "Stamp status failed: $($_.Exception.Message)"
  }
}

# Optional: Redeem a coupon for B
if ($DoRedeem) {
  Write-Step "Redeem a coupon for User B"
  $codeToRedeem = $null
  if ($signup -and $signup.coupon_code) { $codeToRedeem = $signup.coupon_code }
  elseif ($flashCode) { $codeToRedeem = $flashCode }
  else {
    try {
      $my = Invoke-Json -Method GET -Url "$BaseUrl/api/coupons/my/" -Headers $authB -Body $null
      if ($my -and $my.Count -gt 0) { $codeToRedeem = $my[0].code }
    } catch { Write-Warn "Fetching my coupons failed: $($_.Exception.Message)" }
  }
  if (-not $codeToRedeem) {
    Write-Warn "No coupon code available to redeem. Skipping."
  } else {
    try {
      $redeem = Invoke-Json -Method POST -Url "$BaseUrl/api/coupons/redeem/" -Headers $authB -Body @{ coupon_code = $codeToRedeem; restaurant_id = $RestaurantId; pin = $Pin }
      $summary.redeem = @{ coupon_code = $codeToRedeem; result = $redeem }
      Write-Ok ("Redeemed: " + ($redeem | ConvertTo-Json -Depth 5))
    } catch {
      $summary.redeem = @{ coupon_code = $codeToRedeem; error = $_.Exception.Message }
      Write-Warn "Redeem failed: $($_.Exception.Message)"
    }
  }
}

Write-Ok "Flow completed."
if ($JsonOutput) { $summary | ConvertTo-Json -Depth 10 }
