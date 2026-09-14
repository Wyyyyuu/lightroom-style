-- Local, explicit Lightroom SDK commands; diagnostics themselves remain read-only.
local LrApplication = import 'LrApplication'
local LrApplicationView = import 'LrApplicationView'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local Json = dofile(LrPathUtils.child(_PLUGIN.path, 'Json.lua'))
local M = {}

local function trace(message)
    local handle, err = io.open(_PLUGIN.path .. '/bridge-startup.log', 'a')
    if not handle then error('Cannot write plugin startup log: ' .. tostring(err)) end
    handle:write(tostring(message) .. '\n')
    handle:close()
end

local function root()
    return LrPathUtils.child(LrPathUtils.getStandardFilePath('appData'), 'PhotoStyleMatchBridge')
end

local function save(name, result)
    local folder = root()
    local created, createError = LrFileUtils.createAllDirectories(folder)
    if not created then error('Cannot prepare state directory: ' .. folder .. ': ' .. tostring(createError)) end
    -- Each response is new and closed before a ready marker is written.
    local path
    repeat
        _G.photoStyleBridgeSequence = (_G.photoStyleBridgeSequence or 0) + 1
        local filename = string.format('%s-%d-%d.json', name, os.time(), _G.photoStyleBridgeSequence)
        path = LrPathUtils.child(folder, filename)
    until not LrFileUtils.exists(path)
    local handle, err = io.open(path, 'wb')
    if not handle then error(err or 'Cannot create diagnostic response') end
    handle:write(Json.encode(result))
    handle:close()
    local ready, readyError = io.open(path .. '.ready', 'wb')
    if not ready then error(readyError or 'Cannot create response marker') end
    ready:write('ready')
    ready:close()
    return path
end

local function probe(name, action, results)
    local ok, value = LrTasks.pcall(action)
    results[name] = { ok = ok, value = ok and value or nil, error = not ok and tostring(value) or nil }
end

function M.diagnose()
    local result = {
        schema_version = 1,
        bridge_version = '0.2.0',
        command_protocol = 1,
        generated_at_epoch = os.time(),
        plugin_path = _PLUGIN.path,
        scope = 'read-only SDK handshake; no photos modified',
        capabilities = {},
    }
    probe('application_version', function() return LrApplication.versionString() end, result.capabilities)
    probe('active_module', function() return LrApplicationView.getCurrentModuleName() end, result.capabilities)
    probe('catalog', function()
        local catalog = LrApplication.activeCatalog()
        if not catalog then error('No active catalog') end
        local selected = catalog:getTargetPhoto()
        local info = {
            path = catalog:getPath(),
            has_target_photo = selected ~= nil,
            supports_find_by_path = type(catalog.findPhotoByPath) == 'function',
            supports_virtual_copies = type(catalog.createVirtualCopies) == 'function',
        }
        if selected then
            info.target = {
                local_identifier = selected.localIdentifier,
                filename = selected:getFormattedMetadata('fileName'),
                is_virtual_copy = selected:getRawMetadata('isVirtualCopy'),
                supports_apply_settings = type(selected.applyDevelopSettings) == 'function',
            }
            -- Read only selected photo settings. Never enumerate the photo library.
            local settings = selected:getDevelopSettings()
            local subset = {}
            for _, key in ipairs({ 'ProcessVersion', 'Exposure2012', 'Contrast2012', 'Highlights2012', 'Shadows2012', 'Whites2012', 'Blacks2012', 'Temperature', 'Tint', 'Vibrance', 'Saturation' }) do
                local value = settings[key]
                if type(value) == 'number' or type(value) == 'string' or type(value) == 'boolean' then subset[key] = value end
            end
            info.target.settings = subset
        end
        return info
    end, result.capabilities)
    return save('diagnostic', result)
end

function M.start()
    if _G.photoStyleBridgeRunning and _G.photoStyleBridgeWorkerVersion ~= '0.2.0' then
        trace('Stopping previous worker for command protocol upgrade')
        _G.photoStyleBridgeStop = true
        for attempt=1,30 do
            if not _G.photoStyleBridgeRunning then break end
            LrTasks.sleep(0.2)
        end
        if _G.photoStyleBridgeRunning then error('Previous worker did not stop; reload the plugin once') end
    end
    if _G.photoStyleBridgeRunning then trace('Worker already running; start skipped'); return end
    _G.photoStyleBridgeRunning = true
    _G.photoStyleBridgeWorkerVersion = '0.2.0'
    _G.photoStyleBridgeStop = false
    LrTasks.startAsyncTask(function()
        local ok, err = LrTasks.pcall(function()
            trace('Worker entered; state directory: ' .. root())
            save('loaded', { bridge_version = '0.2.0', generated_at_epoch = os.time(), scope = 'plugin loaded; no photos modified', plugin_path = _PLUGIN.path })
            trace('Loaded receipt written')
            M.diagnose()
            trace('Initial diagnostic written; waiting for refresh requests')
            -- Refresh stays read-only. Mutation requests have explicit identity and deadlines.
            local request = LrPathUtils.child(root(), 'refresh.request')
            while not _G.photoStyleBridgeStop do
                if LrFileUtils.exists(request) == 'file' then
                    local removed = LrFileUtils.delete(request)
                    if removed then M.diagnose() end
                end
                dofile(LrPathUtils.child(_PLUGIN.path, 'Commands.lua')).poll(root())
                LrTasks.sleep(1)
            end
        end)
        _G.photoStyleBridgeRunning = false
        if not ok then
            trace('Worker error: ' .. tostring(err))
            LrTasks.pcall(function() save('error', { error = tostring(err), generated_at_epoch = os.time() }) end)
            error(err) -- Let Lightroom's async-task error handler expose the failure too.
        end
    end)
end
return M
