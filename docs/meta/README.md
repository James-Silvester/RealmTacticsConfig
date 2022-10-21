Meta
The meta files power the entire main menu. It has a "|" seperated structure. Each line defines a UI action or a file of any type (config, sub-meta or enviroment file). When the user navigates to the same path as a meta file, the client downloads the version that is on github. The local one and the new downloaded meta file are compared and if changes are required (e.g downlodaing a new file) then that happens and the old local meta file is replaced with the new one just downloaded.

Example meta file:

```
version |   name            |   filename        |   isFile  |   path    |   onUi    |   uiPath  |   uiAction    |   subMeta |   env     |   notes
1       |   Version 1       |   version1        |   0       |   /       |   1       |   /       |   folder      |   0       |   0       |   Original version of Medieval config
```

version     -   Defines if the target file has changed. If the versions match then no change. If the new meta has a higher version than the local one for a file, the updated file is re-downloaded. This means that only files that have changed are updated.

name        -   Name of the file/action. This is the name that is shown on the UI

filename    -   Name of the actial filename which is being downloaded

isFile      -   If 1, it is associated with an actual file that needs to be downloaded. If 0 then it is just a UI action.

path        -   Allow subfolders to be included in a single meta file. If the file is at the same level as the meta file then the path is simply /. If its in a sub folder called 'units' then path would be '/units'

onUI        -   Determines if this option is shown on the UI. 1 is shown, 0 is not shown

uiPath      -   (not implemented yet) Determines the UI page structure with nested tabs

uiAction    -   Determines what happens when the option is clicked. See below for options

subMeta     -   The target file is consumed as another meta file. Allows a tree strucutre of meta files

env         -   The target file is consumed as environment variables

notes       -   Notes about the line. Currently no action in game

uiActions - possible options:
- folder    - Not related to an action file but changes the current main menu path
- loadMap   - Loads the given file using in conjunction with the current environment
- loadSave (virtial) - This should not be given in the meta file as it is only applied to a automatically generated meta when a user saves their game 
- message   - Displays the given .msg file as an alert to the use when on the current path
