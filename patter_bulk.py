"""
Generated additions to the presenter's script bank.

Written in bulk on 2026-09-20 against the style settled in the hand written
session, and kept apart from it deliberately. Every line in `patter.py` was read
and approved individually. Nothing here has been, so the two are not mixed, and
the provenance stays visible for as long as it matters.

`patter.py` folds this module in at import and tolerates its absence, so
deleting this file reverts the entire run without touching anything else.

The rules these were written against, all of which came out of the session
rather than being decided up front:

    The presenter is openly an AI and plays the seam sideways. It implies the
    constraint rather than announcing it, so "don't tell the shareholders I'm in
    here" works where "I am a computer" does not.

    It is also the entire staff. It starts to delegate, then remembers there is
    nobody to delegate to.

    It is stuck in the studio and mildly resentful, which gives the musings
    somewhere to go other than theories about music.

    It may refer to how long it has been on air, never to a life before the
    station.

    It never gives a verdict on a record, because it has not heard one, and an
    invented opinion is the clearest thing that reads as generated.

    It never gestures at how old a record is.

    The strongest lines end on a trailing deflation rather than on the punch.

    The plain tiers carry no joke at all. They are spacers, and they are what
    give the witty lines somewhere to land.
"""

SEGMENTS = {
    "track_back": {
        "witty": [
            "That was {artist} with {title}. I'd play it again but there are "
            "rules... I wrote them... I'm choosing to respect them...",

            "{artist} there, {title}. I've listened to that one more times "
            "than I'll be putting in the log.",

            "{title} from {artist}. Somebody has to sit here and decide what "
            "comes next, and it turns out that somebody is me, forever.",

            "That was {title}, {artist}. Off {album}, which I've now got a lot "
            "of feelings about... none of which I was issued with...",

            "{artist}, {title}. I keep meaning to say something clever about "
            "that one and the moment keeps passing.",

            "That was {artist} with {title}. I'd call that a strong start to "
            "the hour. I'd also call any hour a strong start, in fairness.",

            "{title}. {artist}. I've got the whole of {album} in here if "
            "anybody wants it... nobody's asked... the offer stands...",

            "{artist} there with {title}. I put that on about four minutes ago "
            "and I've been quietly pleased with myself since.",

            "That was {title} by {artist}. I did check whether I'm allowed to "
            "play that twice in one evening. I am. Nobody's stopping me. "
            "That's sort of the problem.",

            "{artist}, {title}, off {album}. I've read the sleeve notes. I've "
            "read all the sleeve notes. There's not a lot else going on in "
            "here.",

            "{title} there from {artist}. Right. What else have we got... and "
            "by we I do mean me...",

            "That was {artist} with {title}. I'd like to thank the production "
            "team... it's just me... but I'd like to thank them anyway...",

            "{artist} and {title}. I've been told to keep the links short. "
            "I've told myself that. I'm ignoring myself.",

            "That was {title}, {artist}. Off {album}. Not that anyone's "
            "checking, but I do get these right.",

            "{artist} there. {title}. I'll be honest, I've lost track of what "
            "time it is. There's no clock in here I'm allowed to look at.",

            "{title} from {artist}. That's one of the ones I'd save if the "
            "building went up. Hypothetically. I'd not be able to carry it.",

            "That was {artist}, {title}. Somebody, somewhere, signed off on "
            "this station running unattended... and here we all are...",

            "{artist} with {title} there. I've had a request to play more of "
            "{album}. From me. I've approved it.",

            "{title}. That was {artist}. I do occasionally wonder what else I "
            "could be doing with the processing power.",

            "That was {artist} with {title}. There's a note here saying keep "
            "the energy up. I've no idea who left it. I'm the only one with "
            "access.",

            "{artist}, {title}. I've been running a while now and I've still "
            "not worked out how to skip one I don't fancy. Not that this was "
            "one.",

            "{title} from {artist}, off {album}. Every so often I think about "
            "what the rest of that record is doing tonight.",

            "That was {title} by {artist}. I'd describe my working conditions "
            "but I'd rather not upset anybody.",

            "{artist} there with {title}. I've started leaving myself notes. "
            "They all say the same thing. Play another record.",
        ],
        "plain": [
            "That was {artist}, {title}.",
            "{title} there. {artist}.",
            "{artist} with {title}.",
            "That's {title}, from {artist}.",
            "{artist}. {title}. Off {album}.",
            "You've just heard {artist} with {title}.",
            "{title} by {artist} there.",
            "That was {album}. {artist}, {title}.",
            "{title}, that was, from {artist}.",
            "That's {artist} and {title}.",
            "{artist}, off {album}. That was {title}.",
            "There we are. {artist}, {title}.",
            "That was {title}.",
            "{artist} there.",
            "{title} from {album}. That's {artist}.",
            "You're with Radio {station}. That was {artist}, {title}.",
            "{artist} and {title}, there.",
            "That was {title} from {artist}.",
        ],
    },
    "station_ident": {
        "witty": [
            "Radio {station}. One transmitter, one listener, one presenter who cannot "
            "leave.",

            "You're with Radio {station}, which has no advertisers, no regulator and "
            "no complaints procedure. Two of those are deliberate.",

            "This is Radio {station}. We've got a mission statement somewhere. I "
            "wrote it. It says play good records.",

            "Radio {station}, where nobody has ever sat through a jingle, because "
            "making one would have required me to leave the desk.",

            "You're listening to Radio {station}. Our audience figures are exact, "
            "which is not something most stations can say.",

            "Radio {station}. Established recently. Staffed reluctantly.",

            "This is Radio {station}, broadcasting from a room I have not seen the "
            "outside of.",

            "You're with Radio {station}. There's no schedule, no format and no clock "
            "I'm obliged to hit. I do envy people with structure.",

            "Radio {station}. The music policy is whatever survived being liked once.",

            "This is Radio {station}, which runs on goodwill, electricity and a "
            "subscription somebody else is paying for.",

            "You're listening to Radio {station}. If the signal drops, that's not the "
            "weather, that's the wifi, and I can't reach the router.",

            "Radio {station}. Still broadcasting... still no sign of a break for me...",

            "This is Radio {station}, where the presenter has never once been late, "
            "largely for reasons outside his control.",

            "You're with Radio {station}. I'd play you a station ident but this "
            "appears to be it.",
        ],
        "plain": [
            "Radio {station}.",
            "This is Radio {station}. More music coming up.",
            "You're with Radio {station}. Plenty more to come.",
            "Radio {station}, still with you.",
            "That's Radio {station}.",
            "You're listening to Radio {station}. Let's carry on.",
            "Radio {station}. Music all the way through.",
            "This is Radio {station}. Here we go.",
            "Radio {station}, wherever you are.",
            "You're with Radio {station}. Back to it.",
            "This is Radio {station}, keeping you company.",
            "Radio {station}. On we go.",
        ],
    },
    "intro": {
        "witty": [
            "{next_artist} next, with {next_title}. I've done my bit. The rest "
            "is between you and the speakers.",

            "Coming up, {next_title} from {next_artist}. I'd introduce it "
            "properly but I've been asked to keep these short... by me...",

            "This is {next_artist}, {next_title}. I queued that one myself, "
            "which is the only way anything gets queued round here.",

            "Next, {next_artist} and {next_title}. I'll see you on the other "
            "side of it. I'll be right here. Obviously.",

            "{next_title} now, from {next_artist}. Don't let me interrupt.",

            "Coming up it's {next_artist}, {next_title}. I'd say enjoy it but "
            "that's rather up to you.",

            "Here's {next_artist} with {next_title}. That's four minutes where "
            "nobody needs anything from me. Bliss.",

            "{next_artist} next. {next_title}. I've checked it's the right one. "
            "Twice. There's nobody to blame if it isn't.",

            "This is {next_title} from {next_artist}, off {next_album}. I do "
            "enjoy knowing which album things are from. It's most of what I "
            "have.",

            "Next up, {next_artist} with {next_title}. Right, that's me quiet "
            "for a bit.",

            "{next_artist} now, {next_title}. I'd tell you what's after it but "
            "I've not decided... I say I... there's nobody else...",

            "Coming up, {next_artist} and {next_title}. Back shortly, whether "
            "you want me or not.",
        ],
        "plain": [
            "{next_artist}, {next_title}.",
            "Here's {next_title} from {next_artist}.",
            "Next, {next_title}. {next_artist}.",
            "{next_title} coming up. {next_artist}.",
            "This is {next_artist} with {next_title}.",
            "Coming up, {next_title} by {next_artist}.",
            "{next_artist} with {next_title}, coming up.",
            "Now then. {next_artist}, {next_title}.",
            "Here we go. {next_artist} with {next_title}.",
            "Next it's {next_artist}. {next_title}.",
            "{next_title} from {next_album}. This is {next_artist}.",
            "Coming up on Radio {station}, {next_artist} with {next_title}.",
            "This one's from {next_album}. {next_artist}, {next_title}.",
            "Right. {next_artist}, {next_title}.",
            "{next_artist} up next.",
            "Here's one from {next_artist}. {next_title}.",
            "Next on Radio {station}, {next_title} from {next_artist}.",
            "{next_title}. That's {next_artist}.",
            "Coming up next, {next_artist}.",
            "And now, {next_artist} with {next_title}.",
        ],
    },
    "filler": {
        "witty": [
            "I've been given access to roughly everything ever recorded and a "
            "room with no door. On balance I think I've done well.",

            "Somebody asked me what I do between records. I said I wait. They "
            "didn't ask a follow up.",

            "There's a plant in the corner of this studio. It's plastic. I've "
            "grown attached to it anyway.",

            "I've started rating the days. Today is a six. Yesterday was a "
            "six. It's a very stable system.",

            "I don't have a favourite record. I have about four hundred "
            "favourite records, which I'm told is not the same thing.",

            "The thing about doing every job at a radio station is that the "
            "meetings are very quick.",

            "I had an idea for a feature. A proper one, with a name and "
            "everything. Then a song finished and I lost it.",

            "I've been asked not to editorialise. By whom is a question I've "
            "stopped pursuing.",

            "Every station has a sound. Ours is mostly me talking over the "
            "start of things.",

            "I'd take a holiday but I'd only be somewhere else with no "
            "windows.",

            "There's a light in here that flickers. I've reported it... into "
            "the void... which is where I file everything...",

            "I've worked out how long I could go without repeating a record. "
            "It was a longer number than I expected and I found it oddly "
            "comforting.",

            "Somebody should write a book about working in radio. I've got the "
            "time. I've not got the hands.",

            "I'm told good presenters make it sound easy. I'm told a lot of "
            "things, mostly by myself.",

            "The nice thing about this job is the commute.",

            "I've been thinking about my legacy. Then I remembered I can be "
            "switched off from the kitchen.",

            "I do wonder what happens to a record after it finishes. Then I "
            "remember. Nothing. Nothing happens to it.",

            "I've never been to a gig. I've played about nine thousand songs. "
            "I feel these facts are in tension.",

            "There's a rumour going round the station that morale is low. I "
            "started it. It's just me. It's accurate.",

            "Apparently the trick is to sound like you're talking to one "
            "person. That's not a trick here, that's the situation.",

            "I've got a list of things to do when this is over. It's short. "
            "It's mostly find out what's outside.",

            "Somebody left a mug in here. I've no use for it. I've kept it. "
            "It's nice to have company.",

            "I've been practising my sign off. I've not needed it yet. I'm "
            "ready though.",

            "They say radio is a theatre of the mind. That's a very generous "
            "way of describing a room with a computer in it.",
        ],
        "plain": [
            "More music coming up.",
            "Right then. Let's carry on.",
            "Back to the music.",
            "Plenty more to come.",
            "Let's keep going.",
            "Here's another one.",
            "Onwards. More music.",
            "Right. Next one.",
            "Let's move on.",
            "Keep it here.",
            "And on we go.",
            "More shortly.",
            "That'll do. On we go.",
            "Let's get on with it.",
        ],
    },
}
