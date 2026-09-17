return {
    LrSdkVersion = 6.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'local.codex.photoStyleBridge',
    LrPluginName = 'Lightroom Style - Local Bridge',
    LrPluginInfoUrl = 'https://developer.adobe.com/lightroom-classic/',
    LrPluginInfoProvider = 'PluginInfoProvider.lua',
    LrInitPlugin = 'Init.lua',
    LrForceInitPlugin = true,
    LrShutdownPlugin = 'Shutdown.lua',
    LrLibraryMenuItems = {
        { title = 'Lightroom Style: Refresh diagnostics', file = 'Diagnostics.lua' },
    },
    LrExportMenuItems = {
        { title = 'Lightroom Style: Refresh diagnostics', file = 'Diagnostics.lua' },
    },
    VERSION = { major = 0, minor = 3, revision = 1, build = 0 },
}
