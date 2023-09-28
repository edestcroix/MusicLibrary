# Music Library

A work-in-progress application to browse and play music from your local music library. Name and most functionallity subject to change.

The base idea is a very simple, paned navigation view that allows filtering by artist -> album -> track only. No other sorting options
are planned on being implemented right now. A play queue to play multiple albums is probably going to happend at some point.

![Screenshot of main window](screenshot.png)

# What is Working
Initial music database generation is working. Right now it is mostly a prototype so as to have some data to work with
to test the UI. Once UI is thought out the requirements of the database will be identified. Currently it can't detect all cover images;
it can't find embedded images or ones not named `cover.jpg`.

Artist and Album lists are working, and selecting artist filters to show only albums by that artist. For the lists, all that is really left
for now is some CSS styling to round image corners, change row margins, etc. In the future sort options will be added, but that's out-of-scope for
right now.

The Album View page is present in a rudimentary state. Basic layout is there, but more prototyping will need to be done to establish a final design.

# What is Not
Any music playback at all has not been implemented yet. Goal is to finish mostly the UI and database first, as playback will
start simple but extra features such as gapless playback will take time to implement.

Refreshing lists takes time right now due to the database not being fully optimized. However, even optimizing it won't make it instant,
so the UI needs to display loading spinners when refreshing the lists.

As mentioned, cover art isn't properly displayed everywhere because some covers aren't found.

Proper handling of multi-artist albums. All but the first artist may either not show up at all or end up in the artist list
but no albums are selectable.

No preferences exist yet. This would be stuff like sort-by options, playback, etc.
