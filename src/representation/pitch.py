#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Represent and interact with pitch: (class, octave, accidental)'''

##-Imports
from math import log2, floor, ceil
from typing_extensions import Self

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

    A4_FREQ = 440 # Hz

    def __init__(self, class_: str | None = None, octave: int | None = None, accid: str | None = None):
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

        if self.accid == 's': # convert s to # (sharp)
            self.accid = '#'

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

        else:
            self.accid = None

        self._check_format()

    def from_class_and_octave(self, class_accid: str, octave: int):
        '''
        Initiates the attributes `class_`, `octave` and `accid` by reading from `class_accid` and `octave`.

        In:
            - class_accid: the class of the note, with the potential accidental, e.g `c#`, or `d`
            - octave: the octave of the note
        '''
    
        self.from_str(f'{class_accid}/{octave}')

    def from_frequency(self, freq: float):
        '''
        Initiates the attributes `class_`, `octave` and `accid` by reading from the frequency `freq`.

        In:
            - freq: the note frequency, in Hz
        '''
    
        # Calculate the number of semitones from A4
        semitones_from_A4 = round(12 * log2(freq / Pitch.A4_FREQ))

        self.from_str('a/4') # Set the current_note to be A4
        self.add_semitones(semitones_from_A4) # And add the right number of semitones to get to the wanted note

    def get_frequency(self) -> float:
        '''
        Calculates the frequency corresponding to the current note.

        Out:
            The frequency of `self`
        '''
    
        if self.class_ is None or self.octave is None:
            raise ValueError('Pitch: get_frequency: attributes `class_` and `octave` should not be None!')
        
        return Pitch.A4_FREQ * (2 ** (self.get_semitones_from_A4() / 12))

    def _get_index(self) -> int:
        '''
        Gets the index in `Pitch.notes_semitones` of the current note (`self.class_` + `self.accid`).

        Out:
            the index of the current note in `Pitch.notes_semitones`
        '''
    
        note = self.get_class_accid()
        return Pitch.notes_semitones.index(note)

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
        Flattens the current pitch (substracts a semitone)
        Calculates the enharmonically equivalent note to `pitch`b.
        '''
    
        self.add_semitones(-1)

    def find_nearby_pitches(self, pitch_distance: float) -> list[Self]:
        '''
        Return a list of all the notes in the range `pitch_distance` of the center note (self).

        The distance function is the interval (number of semitones) between notes.

        In:
            - pitch_distance: the maximum distance allowed, in *tones* (so it is a half integer).

        Out:
            the list of all near notes
        '''

        if self.class_ is None or self.octave is None:
            raise ValueError('Pitch: find_nearby_pitches: attributes `class_` and `octave` should not be None!')

        # Notes semitone by semitone from c
        i = self._get_index() # The relative semitones to the center note
        max_semitone_dist = int(2 * pitch_distance)

        res = []

        for semitone in range(i - max_semitone_dist, i + max_semitone_dist + 1):
            p = Pitch.notes_semitones[semitone % len(Pitch.notes_semitones)]
            o = self.octave + (semitone // len(Pitch.notes_semitones))

            note = Pitch()
            note.from_class_and_octave(p, o)
            res.append(note)

        return res

    def find_frequency_bounds(self, max_distance: float, alpha: float = 0.0) -> tuple[int, int]:
        '''
        Calculates frequencies `f1` and `f2` corresponding to `self - max_distance` and `self + max_distance`.

        In:
            - max_distance: The maximum number of *tones* away from the base note (it is a half integer).
            - alpha: The alpha threshold (0 ≤ alpha ≤ 1).

        Out:
            tuple: A tuple containing the minimum and maximum frequencies (in Hz) as integers.
        '''

        if self.class_ is None or self.octave is None:
            raise ValueError('Pitch: find_nearby_pitches: attributes `class_` and `octave` should not be None!')

        # convert distance to semitones
        effective_distance_semitones =  floor(2 * max_distance * (1 - alpha))

        p1 = self.copy()
        p2 = self.copy()

        p1.add_semitones(-effective_distance_semitones)
        p2.add_semitones(effective_distance_semitones)

        f1 = p1.get_frequency()
        f2 = p2.get_frequency()

        return floor(f1), ceil(f2)

    def get_semitones_from_A4(self) -> int:
        '''
        Calculates the number of semitones between `self` and A4 (440 Hz).

        Out:
            The (signed) number of semitones between the current note and A4: `self - a4`
        '''
    
        a4 = Pitch('a', 4, None)

        return self - a4

    def __sub__(self, other: Self) -> int:
        '''
        Calculate the distance between `self` and `other` in semitones.

        In:
            - other: the other Pitch
        Out:
            the difference in *semitones* with `other`.
        '''

        if self.octave is None or other.octave is None:
            raise ValueError('Pitch: __sub__: octaves must be set!')

        if 'r' in (self.class_, other.class_):
            raise ValueError('Pitch: __sub__: not possible to subtract with a rest!')
    
        return (
            12 * (self.octave - other.octave)
            + self._get_index() - other._get_index()
        )

    def __deepcopy__(self) -> 'Pitch':
        '''Creates a deep copy of self.'''
    
        return Pitch(self.class_, self.octave, self.accid)

    def copy(self) -> 'Pitch':
        return self.__deepcopy__()

    def get_class_accid(self) -> str:
        '''
        Calculates a representation of the note, without the octave, in the format `c#`.
        It always uses sharps.
        '''
    
        if self.class_ == 'r':
            return 'r'
    
        self.add_semitones(0) # Convert to sharp

        if self.accid != None:
            return f'{self.class_}{self.accid}'

        return f'{self.class_}'

    def __repr__(self) -> str:
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

    p_ = Pitch()
    p_.from_frequency(554)
    print(p_)
    print(p_.get_frequency())

    print(p_.find_frequency_bounds(1))

    print(p - p_)
    p.add_semitones(1)
    print(p - p_)
    print(p_ - p)

    p.from_str('c/4')
    p_.from_str('c/5')
    print(p_ - p)

    p.from_str('a/3')
    print(p.get_semitones_from_A4())

    print(p.find_nearby_pitches(.5))

    # c = Pitch('c', 5)
    # print('---')
    # for k in range(24):
    #     print(c)
    #     c.add_semitones(1)
