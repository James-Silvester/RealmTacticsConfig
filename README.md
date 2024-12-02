# Realm Tactics Config

Public repository for the Realm Tactics config. Any configuration on the main branch will be downloaded automatically into the game client when a user navigates to the right menu.

# Quick start to changing game files
- Create a new deveopment branch - ([here is the standard github process to make a new branch for your work](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)).
- Change one of the game files such as [here](https://github.com/James-Silvester/RealmTacticsConfig/tree/main/config/hacktics/version1/entities/types/units). Either one of the `.png` files for graphics  or `.json` files for mechanics.
- Increment the version for the associated line in the meta such as [here](https://github.com/James-Silvester/RealmTacticsConfig/blob/main/config/hacktics/version1/entities/types/meta).
- Commit and push the changes to a your development remote branch
- In the game client, use your new branch `Main Menu` -> `Settings` -> `Main tab` -> `Config branch`
- The new file should be downloaded and can be tested!

# Making changes to files

The game client downloads directly from this repository which powers the menus and each game mode. As a user navigates the menus, meta files are downloaded which defines any other files that also need to be pulled. The meta files define the main menu and what files need downloading and also which files are already the latest version.

An example of defining an archer in a meta file:

```
version | name             | filename    | isFile | path  | onUi | uiPath | action | subMeta | env | notes
1       | Archer Config    | archer.json |   1    | /unit | 1    | /unit  | -      | 0       | 0   | Config for archer unit
1       | Archer ImageFile | archer.png  |   1    | /unit | 0    | /unit  | -      | 0       | 0   | Image for archer unit
```

The most important parts are the version and path+filename in terms of the main development and testing.

The version dictates which version is currently downloaded. If you make a change to one of the files i.e `archer.json` or `archer.png`, a users game client wont download the new version unless the version number is also incremented (in this case to 2). This system means that a users game client wont just keep downloading files that have not be changed - but for development it can be easy to miss updating the meta file version when a file is changed which will lead to the altered file not being picked up!. The filename along with the path dictates where the actual file is in the config directory.

Once the changes are pushed to your branch, give it a minute as github takes a little bit to index it, then run the game client and the new files should be downloaded and used in place of the old ones.

# Testing while developing

For developing and testing purposes, it is possible to test on a branch and configure your game client to utilise the dev branch.

To create a new dev branch, follow the standard [github process to make a new branch for your work](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)

To use the new branch within the game: `Main Menu` -> `Settings` -> `Main tab` -> `Config branch`, your development branch can be selected.

Now, when downloading game files it will download from your branch rather than the main branch. Note: You may find that you will need to click fowards and back a little bit for the new branch files to be picked up.

When development and testing is complete please open a PR using the template to merge into main and make the game changes live.

