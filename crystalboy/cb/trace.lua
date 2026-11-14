-- Crystal Boy: step trace for finding crashes. Each line is written and the file closed before the step runs,
-- so after a crash the last line shows where it stopped. File: config\addons\crystalboy\trace.txt
-- Repeating events (frames) are only written the first few times.
local M = { path = nil, on = true, counts = {} }

function M.start(path)
    M.path = path
    M.last = path:gsub('%.txt$', '') .. '_last.txt'
    M.n = 0
    local f = io.open(path, 'w')
    if f then f:write('Crystal Boy trace ' .. os.date('%Y-%m-%d %H:%M:%S') .. '\n'); f:close() end
end

--- key: repeated events with the same key are written at most `limit` times (default: always)
function M.log(msg, key, limit)
    if not (M.on and M.path) then return end
    if key then
        local n = (M.counts[key] or 0) + 1
        M.counts[key] = n
        if n > (limit or 5) then return end
    end
    local f = io.open(M.path, 'a')
    if f then
        f:write(string.format('%.3f %s\n', os.clock(), tostring(msg)))
        f:close()
    end
end

--- The latest step only (overwritten every time): after a crash it names the step that was running.
function M.step(msg)
    if not (M.on and M.last) then return end
    M.n = (M.n or 0) + 1
    local f = io.open(M.last, 'w')
    if f then f:write(string.format('%d %s\n', M.n, tostring(msg))); f:close() end
end

return M
