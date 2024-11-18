# Realm Tactics Config

Public repository for the Realm Tactics config. Any configuration on the main branch will be downloaded automatically into the game client when a user navigates to the right menu.

# Making changes to files

The game client downloads directly from this repository which powers the menus and each game mode. As a user navigates the menus, meta files are downloaded which defines any other files that also need to be pulled. The meta files define the main menu and what files need downloading and also which files are already the latest version.

An example of defining an archer in a meta file:

```
version | name             | filename    | isFile | path  | onUi | uiPath | action | subMeta | env | notes
1       | Archer Config    | archer.json |   1    | /unit | 1    | /unit  | -      | 0       | 0   | Config for archer unit
1       | Archer ImageFile | archer.png  |   1    | /unit | 0    | /unit  | -      | 0       | 0   | Image for archer unit
```

The most important parts are the version and path+filename in terms of the main development and testing.

The version dictates which version is currently downloaded. If you make a change to one of the files i.e `archer.json` or `archer.png`, a users game client wont download the new version unless the version number is also incremented (in this case to 2). This system means that a users game client wont just keep downloading files but it can be easy to miss updating the version when a file is changed!. The filename along with the path dictates where the actual file is in the config directory.

Once the changes are pushed to your branch, give it a minute as github takes a little bit to index it, then run the game client and the new files should be downloaded and used in place of the old ones.

# Testing while developing

For developing and testing purposes, it is possible to test on a branch and configure your game client to utilise the dev branch.

To create a new dev branch, follow the standard [github process to make a new branch](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)

To use the new branch within the game: Main Menu -> Settings -> Main tab -> Config branch, your development branch can be selected.

Now, when downloading game files it will download from your branch rather than the main branch.

When development and testing is complete please open a PR using the template to merge into main and make the game changes live.

