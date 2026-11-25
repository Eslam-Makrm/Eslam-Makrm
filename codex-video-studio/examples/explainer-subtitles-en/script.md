# How automatic subtitles work

## intro
Most videos on social media are watched with the sound off. [#need] Subtitles keep those viewers.

## listen
First, a speech model called Whisper [#whisper] listens to the voice, and writes down every word [#words] with the moment it was spoken.

## timing
Then the words are grouped into short lines. [#lines] A new line starts wherever the speaker pauses. [#pause]

## outro {hold=1.5}
Finally, the lines are drawn onto the video. [#burn] It all runs on your own computer, for free.
