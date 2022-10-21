Turn Based Stratergy
Turn based stratergy battle config requires json representation of the following features to work:

Entiy Types -- Overall controllers of the base entities that the game consist of. These include all of the different terrain, unit, building types etc.

Entity Tags -- Can be used to define defaults which can be attributed to each entity type. E.e terrain type, unit type, building type etc. Entity types can also have multiple tags e.g <Unit, Infantry, Spy>.

Maps -- Defines the structure and entity content of playable maps. Also contains the team information, win conditions and any information related to playing the particular battle.

AI -- Defines the config which controlles how the AI will play the particular game. This is defined on the version level so will apply to all entities and maps contained within the version

Additional files are required to control the state and flow of the main menu and loading systems:

Meta -- All of the files which are downloaded onto each game client and UI actions such as navigation are handled by the *meta* files. These files control the entire main menu experience and the routes around it.

Env -- There are a set number of enviromental values which are used to tie together required files for use in a single map. When opening any map, there is a set amount of associated configuration (such as entity tags, types and AI config) which is also loaded in by reference through the enviroment variables set.

Msg -- Message files can be used to display an information screen to a user when navigating to a certain path in the menu system
