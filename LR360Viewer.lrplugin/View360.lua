local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrExportSession = import 'LrExportSession'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrDate = import 'LrDate'

local function winQuote(s)
    s = tostring(s)
    return '"' .. s:gsub('"', '""') .. '"'
end

LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    local photos = catalog:getTargetPhotos()
    if not photos or #photos == 0 then
        LrDialogs.message("LR 360 Viewer", "Select one 360 photo first.", "info")
        return
    end

    -- Never write temporary render files inside the plug-in installation folder.
    -- The plug-in may be installed under Program Files or another read-only path.
    -- Lightroom's SDK temp directory is user-writable and appropriate for renders,
    -- sidecars and the temporary launcher used by LR 360 Viewer.
    local tempRoot = LrPathUtils.getStandardFilePath("temp")
    tempRoot = LrPathUtils.child(tempRoot, "LR360Viewer")
    LrFileUtils.createAllDirectories(tempRoot)

    local settings = {
        LR_export_destinationType = "specificFolder",
        LR_export_destinationPathPrefix = tempRoot,
        LR_export_useSubfolder = false,
        LR_collisionHandling = "overwrite",
        LR_format = "JPEG",
        LR_jpeg_quality = 0.95,
        LR_size_doConstrain = false,
        LR_outputSharpeningOn = false,
    }

    local session = LrExportSession {
        photosToExport = { photos[1] },
        exportSettings = settings,
    }

    local renderedPath
    for _, rendition in session:renditions() do
        local ok, result = rendition:waitForRender()
        if not ok then
            LrDialogs.message("LR 360 Viewer", "Render failed:\n\n" .. tostring(result), "critical")
            return
        end
        renderedPath = result
    end

    local photo = photos[1]
    local sourcePath = photo:getRawMetadata("path")
    local sourceFile = renderedPath .. ".source"
    local sf = io.open(sourceFile, "w")
    if sf then sf:write(sourcePath or ""); sf:close() end

    -- Save Perspective requests are signaled by the local viewer.
    LrTasks.startAsyncTask(function()
        local requestFile = renderedPath .. ".import"
        local deadline = LrDate.currentTime() + 21600
        while LrDate.currentTime() < deadline do
            if LrFileUtils.exists(requestFile) then
                local rf = io.open(requestFile, "r")
                local newPath = rf and rf:read("*a") or nil
                if rf then rf:close() end
                pcall(function() LrFileUtils.delete(requestFile) end)
                if newPath and newPath ~= "" and LrFileUtils.exists(newPath) then
                    local ok, err = catalog:withWriteAccessDo("Import 360 Perspective", function()
                        catalog:addPhoto(newPath, photo, "below")
                    end)
                    if not ok then
                        LrDialogs.message("LR 360 Viewer",
                          "JPEG was saved, but Lightroom could not add it to the stack:\n\n"..tostring(err),
                          "warning")
                    end
                end
            end
            LrTasks.sleep(0.5)
        end
    end)

    local launcher = LrPathUtils.child(_PLUGIN.path, "viewer\\LR360Viewer.cmd")
    if not LrFileUtils.exists(launcher) then
        LrDialogs.message("LR 360 Viewer", "Missing viewer launcher:\n\n" .. launcher, "critical")
        return
    end

    -- Build a tiny temporary launcher. This avoids Windows' special
    -- quoting rules for START when both the launcher and image paths contain spaces.
    local runFile = LrPathUtils.child(tempRoot, "_launch360.cmd")
    local f = io.open(runFile, "w")
    if not f then
        LrDialogs.message("LR 360 Viewer", "Could not create temporary launcher.", "critical")
        return
    end
    f:write('@echo off\r\n')
    f:write('call "' .. launcher .. '" "' .. renderedPath .. '"\r\n')
    f:close()

    -- /c accepts one quoted batch path reliably; the batch itself CALLs our viewer.
    local command = 'cmd.exe /d /c ""' .. runFile .. '""'
    LrTasks.execute(command)

end)