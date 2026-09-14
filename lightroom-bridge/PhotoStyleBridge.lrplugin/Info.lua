return {
    LrSdkVersion = 6.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'local.codex.photoStyleBridge',
    LrPluginName = 'Photo Style Match - Local Bridge',
    LrPluginInfoUrl = 'https://developer.adobe.com/lightroom-classic/',
    LrPluginInfoProvider = 'PluginInfoProvider.lua',
    LrInitPlugin = 'Init.lua',
    LrForceInitPlugin = true,
    LrShutdownPlugin = 'Shutdown.lua',
    LrLibraryMenuItems = {
        { title = 'Photo Style Match: Refresh diagnostics', file = 'Diagnostics.lua' },
    },
    LrExportMenuItems = {
        { title = 'Photo Style Match: Refresh diagnostics', file = 'Diagnostics.lua' },
    },
    VERSION = { major = 0, minor = 2, revision = 2, build = 0 },
}
