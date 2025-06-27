#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Represent and interact with pitch: (class, octave, accidental)'''

##-Pitch
class Pitch:
    '''Represent the pitch of a note (class, octave, accidental)'''

    notes_semitones = ('c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b')
    accid_semitones = {
        's': 1,
        '#': 1,
        'b': -1,
        'n': 0,
        'x': 2,
        'bb': -2
    }

    def __init__(self, class_: str | None, octave: int | None, accid: str | None = None):
        '''
        Instantiates the class.

        In:
            - class_: the class of the pitch in (`a`, `b`, `c`, `d`, `e`, `f`, `g`)
            - octave: the octave of the pitch
            - accid: the potential accidental of the note. In (`#`, `s`, `b`, `n`, `x`, `bb`)

        All the arguments can be set to `None` in order to use `self.from_str`.
        '''

        # Check values
        self.class_ = class_
        self.octave = octave
        self.accid = accid

        self._check_format()

    def _check_format(self):
        '''Checks that the attributes `class_` and `accid` are correct (or None)'''
    
        if self.class_ != None and self.class_.lower() not in 'rabcdefg':
            raise ValueError(f'Pitch: error: `class_` must be in (a, b, c, d, e, f, g), but "{self.class_}" found!')

        if self.accid != None and self.accid.lower() not in ('#', 's', 'b', 'f', 'n', 'x', 'bb'):
            raise ValueError(f'Pitch: error: `accid` must be in (#, s, b, n, x, bb), but "{self.accid}" found!')

        if self.accid == '#': # convert # to s (sharp)
            self.accid = 's'

        if self.accid == 'f': # convert f to b (flat)
            self.accid = 'b'

    def from_str(self, note: str | None):
        '''
        Initiates the attributes `class_`, `octave` and `accid` by reading from `note`.

        In:
            - note: the note, represented as `c#/5` for example. A rest is represented as `r`.
        '''

        if note == None:
            self.class_ = None
            self.octave = None
            self.accid = None
            return
    
        note = note.lower()

        if note == 'r':
            self.class_ = 'r'
            self.octave = None
            self.accid = None
            return

        if '/' not in note:
            raise ValueError('Pitch: from_str: argument `note` badly formatted: no slash found')

        cl, octv = note.split('/')

        try:
            self.octave = int(octv)
        except ValueError:
            raise ValueError(f'Pitch: from_str: the octave is not readable from `note` (found "{octv}")')

        self.class_ = cl[0]

        if len(cl) >= 2:
            self.accid = cl[1:]

        self._check_format()

    def add_semitones(self, semitones: int):
        '''
        Adds `semitones` semitones to the current pitch.

        In:
            - semitones: the number of *semitones* to add to self.
        '''

        if self.class_ in (None, 'r'):
            raise ValueError('Pitch: add_semitones: `self.class_` was found to be None, or a rest!')
        if self.octave == None:
            raise ValueError('Pitch: add_semitones: `self.octave` was found to be None!')

        l = len(Pitch.notes_semitones)

        # Take into account the current accidental, if any
        if self.accid != None:
            semitones += Pitch.accid_semitones[self.accid]
    
        # New pitch
        new_pitch = Pitch.notes_semitones[
            (Pitch.notes_semitones.index(self.class_) + semitones) % l
        ]

        # New octave
        octv = self.octave + (Pitch.notes_semitones.index(self.class_) + semitones) // l

        self.from_str(f'{new_pitch}/{octv}')

    def sharpen(self):
        '''
        Sharpens the current pitch (adds a semitone)
        Calculates the enharmonically equivalent note to `pitch`#.
        '''
    
        self.add_semitones(1)

    def flatten(self):
        '''
        Flattens the current pitch (removes a semitone)
        Calculates the enharmonically equivalent note to `pitch`b.
        '''
    
        self.add_semitones(-1)

    def get_class_accid(self) -> str:
        '''
        Calculates a representation of the note, without the octave, in the format `c#`.
        It always uses sharps.
        '''
    
        if self.class_ == 'r':
            return 'r'
    
        self.add_semitones(0) # Convert to sharp

        return f'{self.class_}{self.accid}'

    def __str__(self) -> str:
        '''
        Calculates a representation of the note, in the format `c#/5`.
        It always uses sharps.
        '''

        class_accid = self.get_class_accid()

        if class_accid == 'r':
            return 'r'

        return f'{class_accid}/{self.octave}'

    def to_dict(self) -> dict:
        '''
        Put all the relevant attributes into a dict.
        Used to convert to JSON.
        '''
    
        d = {
            'class': self.class_,
            'octave': self.octave,
            'accid': self.accid
        }

        return d

##-Test
if __name__ == '__main__':
    p = Pitch(None, None)
    p.from_str('db/5')
    print(p)
