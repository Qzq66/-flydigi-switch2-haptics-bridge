$ErrorActionPreference = 'Stop'
$null = [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime]
$null = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime]
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
$manager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$ap = $manager.GetCurrentAccessPointConfiguration()
$ap | Format-List * | Out-String -Width 200
"state=$($manager.TetheringOperationalState) clients=$($manager.ClientCount)"
