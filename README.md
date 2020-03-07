# The OpenMW Ingredient Shuffler

Do you remember what it was like to not know all the important alchemy ingredients? To not have online references and potion calculators?

Do you miss it?

The OpenMW Ingredient Shuffler is for you! It takes all the ingredients, and shuffles their alchemical effects. You won't be able to look them up -- you'll have to advance your alchemy to see them, keep track of them, and figure out your own potion combinations.

This utility is written specifically for [OpenMW](http://openmw.org/) users, and parses openmw.cfg configuration files.

## Features

  - Retains effect frequency. If there's only one ingredient with "Drain Mercantile", there will still be just one after the shuffle. Likewise, "Restore Fatigue" will remain a common first effect.
  - Supports any alchemy mods you're using. It parses all mods you're set up to use, and shuffles accordingly. That is, if you're using Vanilla + a mod that removes all "Fortify Intelligence" effects, you won't see any of those effects post-shuffle, either.
  - Separates food and non-food. Food is more likely to have beneficial first effects, and that was important to retain.
  - Hides cursed items appropriately. An emerald and a cursed emerald should always have the same effects, and the shuffler honors that.

## How to use this

First, make sure you have python (version 3.3 or higher) installed on your system and reachable.

Second, make sure the script itself (`omw_shuffle_ingredients.py`) is downloaded and available. You can download it from github at https://github.com/jmelesky/omw_shuffle_ingredients

Then, [install your mods in the OpenMW way](https://openmw.readthedocs.io/en/latest/reference/modding/index.html), adding `data` lines to your `openmw.cfg`.

Make sure to start the launcher and enable all the appropriate `.esm`, `.esp`, and `.omwaddon` files. Drag them around to the appropriate load order.

Then, run `omw_shuffle_ingredients.py` from a command line (Terminal in OS X, Command Prompt in Windows, etc). This should create a new `.omwaddon` module, and give you instructions on how to enable it.

Open the Launcher, drag the new module to the bottom (it should be loaded after all mods with ingredients in them), and enable it.

Finally, start OpenMW with your new, unique set of ingredient effects.

## Advanced usage

The shuffler should happily work without any arguments, but if you have anything in a non-default location, the following command-line arguments will help:

  - `-c` (or `--configfile`), which allows you to specify a specific config file to use
  - `-d` (or `--moddir`), where you can set the directory in which to put the new mod
  - `-m` (or `--modname`), which lets you set the name of the new mod (it defaults to `Shuffled Ingredients - <today's date>.omwaddon`)

## HELP!

Are you having a problem? I can only fix it if I know about it. You can [file an issue](https://github.com/jmelesky/omw_shuffle_ingredients/issues) on the github project. I'm also trying to be available on the [OpenMW General Discussion forum](https://forum.openmw.org/viewforum.php?f=2), and sometimes on the [#openmw irc channel](https://webchat.freenode.net/?channels=openmw&uio=OT10cnVlde).

## Thanks

  * Resources for understanding MW file formats:
    * http://www.mwmythicmods.com/argent/tech/tute.html
    * http://www.mwmythicmods.com/tutorials/MorrowindESPFormat.html

