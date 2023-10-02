# Music Library

A work-in-progress application to browse and play music from your local music library. Name and most functionallity subject to change.

The base idea is a very simple, paned navigation view that allows filtering by artist -> album -> track only. No other navigation options
are planned on being implemented, but the ability to sort the artist and album lists by different values is planned.

![Screenshot of main window](screenshot.png)

# What is Working
Database generation is mostly working, along with cover art parsing. The parser is able to detect and cache embeded covers and covers in
the same directory as the albums. Now that covers are compressed, RAM usage has gone down from the absolutely ridiculous 1.4GB to around 100MB.

Artist and Album lists are working, and selecting artist filters to show only albums by that artist. For the lists, all that is really left
for now is some CSS styling to round image corners, change row margins, etc. In the future sort options will be added, but that's out-of-scope for
right now.

The Album Overview page is mostly done for now. It's usable. At some point more information will be displayed.

The play queue exists. Currently only albums can be added, not individual tracks. Removing Albums and Tracks work, but removing the
last track of an album doens't remove the album.

# What is Not
Proper playback. Basic playback exists right now (but not comitted to the repo yet) that only plays the first song from the album
and stops. The current implementation needs to be extended to load the next song from the play queue, and the UI elements to seek
and control the playback need to be implemented.

Refreshing the database is slow because it does a complete rebuild of the database. When parsing, there needs to be a better
check to see if a file already exists. A possible way to do this would be to store file modification times, and don't bother
adding a file to the database if the modification time hasn't changed. More thought is needed.

Proper handling of multi-artist albums. All but the first artist may either not show up at all or end up in the artist list
but no albums are selectable. Also, albums with multiple discs aren't handled correctly. For one, discnumber isn't tracked in
the database. Secondly, there is no way to display discs in the UI yet. (Which wouldn't be too hard after the database stores it)

No preferences exist yet. This would be stuff like sort-by options, playback, etc.
