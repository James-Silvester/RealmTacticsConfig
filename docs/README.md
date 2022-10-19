Turn Based Stratergy
Turn based stratergy battle config requires json representation of the following features to work:

Entiy Types -- Overall controllers of the base entities that the game consist of. These include all of the different terrain, unit, building types etc.

Entity Tags -- Can be used to define defaults which can be attributed to each entity type. E.e terrain type, unit type, building type etc. Entity types can also have multiple tags e.g <Unit, Infantry, Spy>.

Maps -- Defines the structure and entity content of playable maps. Also contains the team information, win conditions and any information related to playing the particular battle.

AI -- Defines the config which controlles how the AI will play the particular game. This is defined on the version level so will apply to all entities and maps contained within the version