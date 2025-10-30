# # Test 1: Check if Set-Cookie headers are being sent
# Write-Host "`n=== TEST 1: Testing Set-Cookie Headers ===" -ForegroundColor Cyan

# $response = Invoke-WebRequest -Uri "http://localhost:9090/api/test-cookies/" `
#   -Method POST `
#   -Headers @{"Content-Type"="application/json"} `
#   -Body '{"key":"value"}' `
#   -SessionVariable session

# Write-Host "`nResponse Status: $($response.StatusCode)" -ForegroundColor Green
# Write-Host "`nSet-Cookie Headers:" -ForegroundColor Yellow
# $response.Headers['Set-Cookie'] | ForEach-Object { Write-Host "  $_" }

# Write-Host "`nCookies in Session:" -ForegroundColor Yellow
# $session.Cookies.GetCookies("http://localhost:9090") | ForEach-Object {
#   Write-Host "  Name: $($_.Name), Value: $($_.Value), Secure: $($_.Secure), HttpOnly: $($_.HttpOnly)"
# }

# # Test 2: Try to login and capture cookies
# Write-Host "`n`n=== TEST 2: Testing Login with Cookies ===" -ForegroundColor Cyan

# $loginBody = @{
#   email = "support@prolianceltd.com"  # Replace with actual test email
#   password = "qwerty"  # Replace with actual password
# } | ConvertTo-Json

# try {
#   $loginResponse = Invoke-WebRequest -Uri "http://localhost:9090/api/token/" `
#     -Method POST `
#     -Headers @{"Content-Type"="application/json"} `
#     -Body $loginBody `
#     -SessionVariable loginSession

#   Write-Host "`nLogin Status: $($loginResponse.StatusCode)" -ForegroundColor Green
  
#   Write-Host "`nSet-Cookie Headers from Login:" -ForegroundColor Yellow
#   $loginResponse.Headers['Set-Cookie'] | ForEach-Object { Write-Host "  $_" }

#   Write-Host "`nCookies Stored After Login:" -ForegroundColor Yellow
#   $loginSession.Cookies.GetCookies("http://localhost:9090") | ForEach-Object {
#     Write-Host "  Name: $($_.Name)"
#     Write-Host "    Value: $($_.Value.Substring(0, [Math]::Min(50, $_.Value.Length)))..."
#     Write-Host "    Secure: $($_.Secure)"
#     Write-Host "    HttpOnly: $($_.HttpOnly)"
#     Write-Host "    Domain: $($_.Domain)"
#     Write-Host "    Path: $($_.Path)"
#   }

#   # Test 3: Use cookies to validate token
#   Write-Host "`n`n=== TEST 3: Testing Token Validation with Cookies ===" -ForegroundColor Cyan

#   $validateResponse = Invoke-WebRequest -Uri "http://localhost:9090/api/token/validate/" `
#     -Method GET `
#     -WebSession $loginSession

#   Write-Host "`nValidation Status: $($validateResponse.StatusCode)" -ForegroundColor Green
#   Write-Host "`nValidation Response:" -ForegroundColor Yellow
#   Write-Host $validateResponse.Content

# } catch {
#   Write-Host "`nError during login test:" -ForegroundColor Red
#   Write-Host $_.Exception.Message
#   if ($_.Exception.Response) {
#     $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
#     $reader.BaseStream.Position = 0
#     $responseBody = $reader.ReadToEnd()
#     Write-Host "Response Body: $responseBody" -ForegroundColor Red
#   }
# }

# # Test 4: Check CORS preflight
# Write-Host "`n`n=== TEST 4: CORS Preflight Check ===" -ForegroundColor Cyan

# $corsResponse = Invoke-WebRequest -Uri "http://localhost:9090/api/token/" `
#   -Method OPTIONS `
#   -Headers @{
#     "Origin" = "http://localhost:5173"
#     "Access-Control-Request-Method" = "POST"
#     "Access-Control-Request-Headers" = "content-type"
#   }

# Write-Host "`nCORS Status: $($corsResponse.StatusCode)" -ForegroundColor Green
# Write-Host "`nCORS Headers:" -ForegroundColor Yellow
# $corsResponse.Headers.GetEnumerator() | Where-Object { $_.Key -like "*access-control*" } | ForEach-Object {
#   Write-Host "  $($_.Key): $($_.Value)"
# }

# Write-Host "`n`n=== All Tests Complete ===" -ForegroundColor Cyan