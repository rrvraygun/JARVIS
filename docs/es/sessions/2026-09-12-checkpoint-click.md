# Checkpoint click regression

The report that a checkpoint click registered but showed no options was traced
to duplicate event handling. ConversationCheckpointControl and JarvisTui both
handled the same button event; depending on Textual propagation, one handler
could open the menu and the other close it again.

The child handler is now the sole route and calls `_toggle_checkpoint`
synchronously, so the menu state changes in the same click event. The button
remains the first child; the OptionList is the second child and is positioned
below it. The control keeps a fixed height while open; its menu has a fixed
four-line height and does not change conversation width. A second click closes
it. The application no longer has a competing checkpoint handler.

The graphical regression verifies button dimensions, menu attachment and
visibility, menu placement below the button, and close-on-second-click. The
focused test passes. No system files, root helpers or credentials changed.
