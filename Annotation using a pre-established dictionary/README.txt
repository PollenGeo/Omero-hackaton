Species Autocomplete fo OMERO v2.0
---------------------------------------------------------------

Overview

The Species Autocomplete Extension helps users autocomplete genus and species names on webpages to prevent misspelling or incosisntent names by referencing a preloaded list. This list must be updated from a CSV file, this CSV file must have only one column with the name of the taxa and no header. 
The extension was created focused on creating consistent OMERO tags (for palynologcal taxonomy).
!!!The current version of the extension ONLY supports Google Chrome browser and Chromiun based browsers like Microsoft Edge .¡¡¡

Features:

-Works on any text input or textarea on any webpage (created focusing on OMERO tags).
-Shows suggestions as you type.
-Clicking a suggestion fills in the input.
-Suggestions follow the input as you scroll.
-Limited to 15 suggestions at a time for performance.
-Persists species list across browser sessions.
-Can be activated and deactivated with a button.
-Lets the user select the separator of the CSV file.
-Shows the number of species loaded (excludes duplicates).
-Shows first the last species selected by the user.

Installation:

-Open Chrome and go to chrome://extensions/.
-Enable Developer mode (toggle in the top right).
-Click on Load unpacked and select the folder "species-autocomplete" that is in the same folder as this txt file.
-The extension icon should now appear in your browser toolbar, indicating it is ready for use.

Usage:

-Click the extension icon in your browser toolbar.
-Select the separator of your CSV file.
-Upload your species list .csv file that must have only one column with the name of the taxa and no header.
-The popup will display the number of species loaded and ahow a preview of the parsed data.
-In the popup, you will see a button labeled "Autocomplete Active" (green) or "Autocomplete inactive" (red):
--Click "Autocomplete inactive" to activate the autocomplete feature.
--Click "Autocomplete Active" to deactivate it.
-When active, the extension will automatically suggest species names based on the data you've loaded.

Check that the necessary permissions are enabled for the extension to access the target pages.

If you need to update the species list, add the new CSV file and reload the extension.
Confirm the species count has updated in the popup.

Additional Notes
Privacy: The extension does not store or transmit any personal data (The extension works locally).
Icon image: Picture of a pollen grain of Grimsdalea magnaclavata, taken with Confocal microscopy, Pollen Geo.
Permissions: The extension requires access to local storage and access to specific webpages to enable autocomplete functionality.
Version: 2
Author: David Caro
Author email: decaroc@unal.edu.co



