-- A direct, module-independent entry point in Lightroom's Plug-in Manager.
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local function runDiagnostic(properties)
    if properties.bridgeBusy then return end
    properties.bridgeBusy = true
    properties.bridgeStatus = '正在运行只读检查……'
    LrTasks.startAsyncTask(function()
        local ok, result = LrTasks.pcall(function()
            local log, err = io.open(_PLUGIN.path .. '/bridge-startup.log', 'a')
            if not log then error('Cannot write manager diagnostic log: ' .. tostring(err)) end
            log:write('Plugin Manager diagnostic button selected\n')
            log:close()
            local bridge = dofile(_PLUGIN.path .. '/Bridge.lua')
            bridge.start()
            return bridge.diagnose()
        end)
        properties.bridgeBusy = false
        if ok then
            properties.bridgeStatus = '已生成 SDK 诊断回执（不代表调色或导出已验证）：\n' .. tostring(result)
        else
            properties.bridgeStatus = '检查失败，请保留以下错误：\n' .. tostring(result)
        end
    end)
end

return {
    startDialog = function(properties)
        properties.bridgeBusy = false
        properties.bridgeStatus = '尚未运行检查。此操作只读取当前照片的部分参数，不修改照片。'
    end,
    sectionsForTopOfDialog = function(factory, properties)
        return {
            {
                title = 'Photo Style Match 连接诊断 · 0.2.0.1',
                factory:push_button {
                    title = '运行只读连接检查',
                    action = function() runDiagnostic(properties) end,
                },
                factory:static_text {
                    bind_to_object = properties,
                    title = LrView.bind('bridgeStatus'),
                    width_in_chars = 68,
                    height_in_lines = 5,
                },
            },
        }
    end,
}
