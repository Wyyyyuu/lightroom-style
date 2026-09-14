local LrPathUtils = import 'LrPathUtils'
local LrTasks = import 'LrTasks'
local log, err = io.open(_PLUGIN.path .. '/bridge-startup.log', 'a')
if not log then error('Cannot write manual diagnostic log: ' .. tostring(err)) end
log:write('Manual diagnostics menu selected\n')
log:close()
LrTasks.startAsyncTask(function()
    local bridge = dofile(LrPathUtils.child(_PLUGIN.path, 'Bridge.lua'))
    bridge.start()
    bridge.diagnose()
end)
